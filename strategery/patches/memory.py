import json
from datetime import datetime, timedelta
from .base import BasePatch
from .lifecycle import lifecycle_manager
from .config import load_strategic_context
from .vsa import VectorStoreFactory
from strategery.strategic_logger import strategic_logger

def strategic_prune_context(messages, ttl_hours, keep_last_assistants):
    """
    Prunes a list of messages based on TTL and mandatory retention of recent assistant turns.
    Returns: A new list of pruned messages.
    """
    cutoff = datetime.now() - timedelta(hours=ttl_hours)
    
    new_msgs = []
    assistant_count = 0
    needed_tool_ids = set()
    
    # Pass 1: Identification (Reverse to find newest first)
    for m in reversed(messages):
        role = m.get("role")
        
        # Ensure timestamp is parsed
        if "_parsed_ts" not in m and m.get("timestamp"):
            try: m["_parsed_ts"] = datetime.fromisoformat(m["timestamp"])
            except: m["_parsed_ts"] = None
        
        is_old = m.get("_parsed_ts") and m["_parsed_ts"] < cutoff
        
        keep = False
        if role == "user":
            keep = True
        elif role == "assistant":
            assistant_count += 1
            if not is_old or assistant_count <= keep_last_assistants:
                keep = True
                for tc in (m.get("tool_calls") or []):
                    if tid := tc.get("id"): needed_tool_ids.add(tid)
        
        if keep:
            new_msgs.append(m)
            
    # Pass 2: Tool Resolution (Forward to preserve order)
    final_msgs = []
    for m in messages:
        role = m.get("role")
        if m in new_msgs:
            final_msgs.append(m)
        elif role == "tool" and m.get("tool_call_id") in needed_tool_ids:
            final_msgs.append(m)
            
    # Cleanup temporary metadata
    for m in final_msgs:
        m.pop("_parsed_ts", None)
        
    return final_msgs

def strategic_format_consolidation_messages(messages):
    """Formats a list of messages into a string for the consolidator prompt."""
    lines = []
    for m in messages:
        if not m.get("content"): continue
        role = m["role"].upper()
        content = m["content"]
        lines.append(f"[{m.get('timestamp', '?')[:16]}] {role}: {content}")
    return "\n".join(lines)

def strategic_parse_consolidation_response(content, has_tool_calls, tool_arguments, current_memory):
    """
    Parses the LLM response (from tool calls or raw text) and applies regex recovery.
    Returns: A dict with 'history_entry' and 'memory_update' or None if invalid.
    """
    args = None
    if has_tool_calls:
        args = tool_arguments
        if isinstance(args, str):
            try: args = json.loads(args)
            except: pass

    # Regex Recovery if tool call failed or we have raw text
    if not args or not isinstance(args, dict):
        try:
            import re
            match = re.search(r"\{.*\}", str(content), re.DOTALL)
            if match:
                candidate = json.loads(match.group(0))
                args = {
                    "history_entry": candidate.get("history_entry") or candidate.get("summary") or "No summary available.",
                    "memory_update": candidate.get("memory_update") or candidate.get("facts") or current_memory
                }
        except: pass

    if args and isinstance(args, dict) and ("history_entry" in args or "memory_update" in args):
        return args
    return None

def strategic_get_rolling_journal(storage_root, max_chars=1000):
    """
    Reads the last N characters from the current day's journal for chronological continuity.
    Returns: A formatted string or empty if no journal exists.
    """
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        journal_path = storage_root / "workspace" / "memory" / f"{today}.md"

        # BUG-095: Initialize the daily journal if it doesn't exist or is empty
        if not journal_path.exists() or journal_path.stat().st_size == 0:
            try:
                journal_path.parent.mkdir(parents=True, exist_ok=True)
                with open(journal_path, "w", encoding="utf-8-sig") as f:
                    f.write(f"# {today}\n\n")
            except Exception as e:
                strategic_logger.error(f"Failed to initialize daily journal: {e}")
            return ""

        with open(journal_path, "r", encoding="utf-8-sig") as f:            content = f.read()
            
        if not content:
            return ""
            
        # Extract the last part of the file
        snippet = content[-max_chars:]
        if len(content) > max_chars:
            # Try to find the first newline to avoid mid-line cuts
            nl_pos = snippet.find("\n")
            if nl_pos != -1:
                snippet = snippet[nl_pos+1:]
                
        return f"\n### RECENT CONTINUITY (FROM DAILY JOURNAL):\n...{snippet}\n"
    except Exception as e:
        strategic_logger.error(f"Error reading rolling journal: {e}")
        return ""

def strategic_write_journal_entry(storage_root, entry):
    """Writes a consolidation entry to the daily journal."""
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        journal_path = storage_root / "workspace" / "memory" / f"{today}.md"
        journal_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(journal_path, "a", encoding="utf-8-sig") as f:
            ts = datetime.now().strftime("%H:%M:%S")
            f.write(f"\n### CONSOLIDATION [{ts}]\n{entry}\n")
        return True
    except Exception as e:
        strategic_logger.error(f"Failed to write journal entry: {e}")
        return False

async def strategic_inject_rag_context(content, provider, vec_store_factory=VectorStoreFactory):
    """
    Queries the vector store and returns formatted context to inject.
    Returns (injected_block, count) or (None, 0).
    """
    # HARDENING: Avoid triggering RAG for short or generic messages that drown context
    is_generic = content.lower().strip() in ["yes", "no", "ok", "okay", "hello", "hi", "thanks", "thank you", "confirmed"]
    if len(content) <= 10 or is_generic or content == "[empty message]":
        return None, 0

    try:
        vec_store = vec_store_factory.get_store(provider=provider)
        results = await vec_store.query(content, n_results=3)
        
        if results:
            # Filter out 'No summary available' and empty content
            valid_results = [r for r in results if r.get('content') and "No summary available" not in r['content']]
            
            if valid_results:
                context_lines = []
                for r in valid_results:
                    context_lines.append(f"- {r['content']}")
                
                # Warning about potentially stale data
                warning = "[STRATEGIC MEMORY - MAY BE STALE OR OUTDATED. USE RESEARCH TOOLS TO VERIFY.]\n"
                mem_block = "### RETRIEVED HISTORICAL CONTEXT:\n" + warning + "\n".join(context_lines)
                return mem_block, len(valid_results)
    except Exception as re:
        strategic_logger.error(f"Semantic Retrieval error: {re}")
    
    return None, 0

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
            strategic_logger.error(f"Memory patch error: {e}")
            return False

    def _patch_memory_consolidation(self, config_data):
        from nanobot.agent.memory import MemoryStore, _SAVE_MEMORY_TOOL
        
        if not hasattr(MemoryStore, "_orig_consolidate_strategic"):
            MemoryStore._orig_consolidate_strategic = MemoryStore.consolidate

            async def _patched_consolidate(self, session, provider, model, **kwargs):
                config_model = config_data.get("agents", {}).get("consolidator", {}).get("model")
                if config_model:
                    model = config_model
                    strategic_logger.info(f"Memory consolidation forced to model: {model}")

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

                lines_str = strategic_format_consolidation_messages(old_messages)
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
{lines_str}

### FINAL MANDATE:
- Do NOT repeat yourself.
- Output ONLY the raw JSON object.
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

                    tool_args = response.tool_calls[0].arguments if response.has_tool_calls else None
                    args = strategic_parse_consolidation_response(response.content, response.has_tool_calls, tool_args, current_memory)

                    if not args:
                        strategic_logger.warning(f"Consolidator failed to parse response.")
                        return False

                    try:
                        import asyncio
                        # Ensure provider has the strategic embed method
                        if not hasattr(provider, "embed"):
                            from strategery.patches.provider import strategic_litellm_embed
                            provider.embed = strategic_litellm_embed.__get__(provider, type(provider))
                        
                        vec_store = VectorStoreFactory.get_store(provider=provider)
                        entry = args.get("history_entry", "No summary available.")
                        update = args.get("memory_update", current_memory)
                        
                        # 1. Push to Vector Store
                        asyncio.create_task(vec_store.add_entry(str(entry), {"type": "history_summary", "source": "consolidation"}))
                        
                        # 2. Write to Daily Journal
                        _, _, storage_root = load_strategic_context()
                        strategic_write_journal_entry(storage_root, entry)
                        
                        # 3. Update Long-Term Memory
                        if update and update != current_memory:
                            self.write_long_term(str(update))
                            asyncio.create_task(vec_store.add_entry(f"UPDATED CORE MEMORY:\n{update}", {"type": "memory_fact_sheet"}))

                        strategic_logger.info(f"Strategic Consolidation complete.")
                    except Exception as ve:
                        strategic_logger.error(f"Strategic Memory persistence error: {ve}")

                    session.last_consolidated = 0 if archive_all else len(session.messages) - keep_count
                    return True
                except Exception as e:
                    strategic_logger.error(f"Memory consolidation error: {e}")
                    return False

            MemoryStore.consolidate = _patched_consolidate

    def _patch_context_pruning(self, config_data):
        from nanobot.agent.loop import AgentLoop
        
        if not hasattr(AgentLoop, "_orig_process_message_strategic"):
            AgentLoop._orig_process_message_strategic = AgentLoop._process_message

            async def _patched_process_message(self, msg, session_key=None, on_progress=None):
                # Identify internal/system channels to skip noise injection (BUG-083)
                is_internal = msg.channel in {"system", "cron", "heartbeat"} or msg.sender_id == "subagent"
                original_content = msg.content or ""

                # 0. Rolling Journal Injection (Skip for internal)
                if not is_internal:
                    try:
                        _, _, storage_root = load_strategic_context()
                        journal_snippet = strategic_get_rolling_journal(storage_root)
                        if journal_snippet:
                            msg.content = journal_snippet + "\n" + msg.content
                    except Exception as je:
                        strategic_logger.error(f"Rolling Journal injection failed: {je}")

                # 1. Context Pruning
                prune_cfg = config_data.get("agents", {}).get("defaults", {}).get("contextPruning", {})
                if prune_cfg.get("enabled"):
                    key = session_key or msg.session_key
                    session = self.sessions.get_or_create(key)
                    ttl_str = prune_cfg.get("ttl", "6h")
                    hours = int(ttl_str[:-1]) if ttl_str.endswith("h") else 6
                    keep_last = prune_cfg.get("keepLastAssistants", 3)
                    session.messages = strategic_prune_context(session.messages, hours, keep_last)

                # 2. Semantic Retrieval (RAG) (Skip for internal)
                rag_cfg = config_data.get("strategic_edition", {}).get("memory_rag", {})
                if rag_cfg.get("enabled", True) and not is_internal:
                    # BUG FIX: Evaluate RAG skip against original content (BUG-097)
                    rag_block, count = await strategic_inject_rag_context(original_content, self.provider)
                    if rag_block:
                        msg.content = rag_block + "\n\n" + msg.content
                        strategic_logger.info(f"RAG: Injected {count} relevant facts.")

                # 3. Memory Flush
                flush_cfg = config_data.get("agents", {}).get("defaults", {}).get("compaction", {}).get("memoryFlush", {})
                if flush_cfg.get("enabled"):
                    key = session_key or msg.session_key
                    session = self.sessions.get_or_create(key)
                    unconsolidated = len(session.messages) - session.last_consolidated
                    if unconsolidated >= (self.memory_window * 0.8):
                        strategic_logger.info(f"Memory Flush triggered.")
                        flush_prompt = flush_cfg.get("prompt", "Store durable memories now.")
                        sys_prompt = flush_cfg.get("systemPrompt", "Session nearing compaction.")
                        
                        hardened_sys_prompt = (
                            f"{sys_prompt}\n\n"
                            "### ⚖️ STRATEGIC MANDATE (FLUSH MODE):\n"
                            "1. DO NOT use 'exec' to write to HISTORY.md or any log files.\n"
                            "2. DO NOT attempt to 'save' memory yourself. The system's automated 'save_memory' protocol will handle this.\n"
                            "3. Your ONLY task is to provide a brief acknowledgement or a final thought before the session is compacted.\n"
                            "4. STOP your turn immediately after your response."
                        )
                        
                        history = session.get_history(max_messages=self.memory_window)
                        flush_msgs = self.context.build_messages(
                            history=history,
                            current_message=f"""### SYSTEM NOTIFICATION: {hardened_sys_prompt}

{flush_prompt}""",
                            channel=msg.channel, chat_id=msg.chat_id
                        )
                        res, _, all_msgs = await self._run_agent_loop(flush_msgs)
                        if res and res != "NO_REPLY":
                            self._save_turn(session, all_msgs, 1 + len(history))
                        await self._consolidate_memory(session)

                return await self._orig_process_message_strategic(msg, session_key, on_progress)

            AgentLoop._process_message = _patched_process_message
