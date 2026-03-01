import json
from datetime import datetime, timedelta
from . import BasePatch

class MemoryPatch(BasePatch):
    """Handles memory consolidation, context pruning, and memory flush patches."""
    
    @property
    def name(self) -> str:
        return "Memory & Context Management"

    def apply(self, config_data: dict) -> bool:
        try:
            self._patch_memory_consolidation(config_data)
            self._patch_context_pruning(config_data)
            return True
        except Exception as e:
            print(f"[Launcher] Memory patch error: {e}")
            return False

    def _patch_memory_consolidation(self, config_data):
        from nanobot.agent.memory import MemoryStore, _SAVE_MEMORY_TOOL
        
        if not hasattr(MemoryStore, "_orig_consolidate_strategic"):
            MemoryStore._orig_consolidate_strategic = MemoryStore.consolidate

            async def _patched_consolidate(self, session, provider, model, **kwargs):
                config_model = config_data.get("agents", {}).get("consolidator", {}).get("model")
                if config_model:
                    model = config_model
                    print(f"[Launcher] Memory consolidation forced to model: {model}")

                archive_all = kwargs.get("archive_all", False)
                memory_window = kwargs.get("memory_window", 50)

                if archive_all:
                    old_messages = session.messages
                    keep_count = 0
                else:
                    keep_count = memory_window // 2
                    if len(session.messages) <= keep_count: return True
                    old_messages = session.messages[session.last_consolidated:-keep_count]
                    if not old_messages: return True

                lines = []
                for m in old_messages:
                    if not m.get("content"): continue
                    role = m["role"].upper()
                    content = m["content"]
                    lines.append(f"[{m.get('timestamp', '?')[:16]}] {role}: {content}")

                current_memory = self.read_long_term()

                prompt = f"""You are a senior memory consolidation specialist. Your goal is to extract durable, high-value information from the conversation history and merge it into the existing long-term memory.

### REQUIRED OUTPUT FORMAT (STRICT JSON ONLY):
{{
  "history_entry": "A concise, 1-2 sentence summary of key actions or decisions in this segment.",
  "memory_update": "The complete, updated block of long-term memory. You MUST preserve all existing facts while adding new insights. Format as a clean, bulleted list of facts, preferences, and project states."
}}

### CURRENT LONG-TERM MEMORY:
{current_memory or "(empty)"}

### NEW CONVERSATION SEGMENT:
{chr(10).join(lines)}

### FINAL MANDATE:
- Do NOT repeat yourself.
- Do NOT provide conversational filler.
- Output ONLY the raw JSON object. Any text outside the JSON will be considered a failure.
"""
                try:
                    response = await provider.chat(
                        messages=[
                            {"role": "system", "content": "You are a JSON-only response agent. You MUST provide valid JSON matching the requested schema. No conversational text."},
                            {"role": "user", "content": prompt},
                        ],
                        tools=_SAVE_MEMORY_TOOL,
                        model=model,
                    )

                    args = None
                    text = response.content or ""
                    if response.has_tool_calls:
                        args = response.tool_calls[0].arguments
                        if isinstance(args, str):
                            try: args = json.loads(args)
                            except: pass

                    if not args or not isinstance(args, dict):
                        print(f"[Launcher] Warning: Consolidator failed tool call. Attempting Regex Recovery on: {text[:200]}...")
                        try:
                            import re
                            match = re.search(r"\{.*\}", text, re.DOTALL)
                            if match:
                                candidate = json.loads(match.group(0))
                                args = {
                                    "history_entry": candidate.get("history_entry") or candidate.get("summary") or "No summary available.",
                                    "memory_update": candidate.get("memory_update") or candidate.get("facts") or current_memory
                                }
                        except: pass

                    if not args or not isinstance(args, dict):
                        return False

                    if entry := args.get("history_entry"):
                        self.append_history(str(entry))
                    if update := args.get("memory_update"):
                        if update != current_memory:
                            self.write_long_term(str(update))

                    session.last_consolidated = 0 if archive_all else len(session.messages) - keep_count
                    print(f"[Launcher] Memory consolidation SUCCESSFUL.")
                    return True
                except Exception as e:
                    print(f"[Launcher] Memory consolidation error: {e}")
                    return False

            MemoryStore.consolidate = _patched_consolidate

    def _patch_context_pruning(self, config_data):
        from nanobot.agent.loop import AgentLoop
        
        if not hasattr(AgentLoop, "_orig_process_message_strategic"):
            AgentLoop._orig_process_message_strategic = AgentLoop._process_message

            async def _patched_process_message(self, msg, session_key=None, on_progress=None):
                # 1. Context Pruning
                prune_cfg = config_data.get("agents", {}).get("defaults", {}).get("contextPruning", {})
                if prune_cfg.get("enabled"):
                    key = session_key or msg.session_key
                    session = self.sessions.get_or_create(key)
                    ttl_str = prune_cfg.get("ttl", "6h")
                    hours = int(ttl_str[:-1]) if ttl_str.endswith("h") else 6
                    cutoff = datetime.now() - timedelta(hours=hours)
                    
                    new_msgs = []
                    assistant_count = 0
                    needed_tool_ids = set()
                    
                    # Pass 1: Identification
                    for m in reversed(session.messages):
                        role = m.get("role")
                        if "_parsed_ts" not in m and m.get("timestamp"):
                            try: m["_parsed_ts"] = datetime.fromisoformat(m["timestamp"])
                            except: m["_parsed_ts"] = None
                        
                        is_old = m.get("_parsed_ts") and m["_parsed_ts"] < cutoff
                        
                        keep = False
                        if role == "user":
                            keep = True
                        elif role == "assistant":
                            assistant_count += 1
                            if not is_old or assistant_count <= prune_cfg.get("keepLastAssistants", 3):
                                keep = True
                                for tc in (m.get("tool_calls") or []):
                                    if tid := tc.get("id"): needed_tool_ids.add(tid)
                        
                        if keep:
                            new_msgs.append(m)
                    
                    # Pass 2: Tool Resolution
                    final_msgs = []
                    for m in session.messages:
                        role = m.get("role")
                        if m in new_msgs:
                            final_msgs.append(m)
                        elif role == "tool" and m.get("tool_call_id") in needed_tool_ids:
                            final_msgs.append(m)
                    
                    if len(final_msgs) < len(session.messages):
                        session.messages = final_msgs

                # 2. Memory Flush
                flush_cfg = config_data.get("agents", {}).get("defaults", {}).get("compaction", {}).get("memoryFlush", {})
                if flush_cfg.get("enabled"):
                    key = session_key or msg.session_key
                    session = self.sessions.get_or_create(key)
                    unconsolidated = len(session.messages) - session.last_consolidated
                    if unconsolidated >= (self.memory_window * 0.8):
                        print(f"[Launcher] Memory Flush triggered.")
                        flush_prompt = flush_cfg.get("prompt", "Store durable memories now.")
                        sys_prompt = flush_cfg.get("systemPrompt", "Session nearing compaction.")
                        history = session.get_history(max_messages=self.memory_window)
                        flush_msgs = self.context.build_messages(
                            history=history,
                            current_message=f"""### SYSTEM NOTIFICATION: {sys_prompt}

{flush_prompt}""",
                            channel=msg.channel, chat_id=msg.chat_id
                        )
                        res, _, all_msgs = await self._run_agent_loop(flush_msgs)
                        if res and res != "NO_REPLY":
                            self._save_turn(session, all_msgs, 1 + len(history))
                        await self._consolidate_memory(session)

                # Strip temporary timestamps
                key = session_key or msg.session_key
                session = self.sessions.get_or_create(key)
                for m in session.messages:
                    m.pop("_parsed_ts", None)

                return await self._orig_process_message_strategic(msg, session_key, on_progress)

            AgentLoop._process_message = _patched_process_message
