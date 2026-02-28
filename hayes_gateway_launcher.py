import asyncio
import sys
import runpy
import os
import json
import io
from pathlib import Path

# Force UTF-8 encoding for Windows stdout/stderr to prevent charmap errors
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 1. Fix the Windows 'Event loop is closed' error while supporting subprocesses
if sys.platform == 'win32':
    # WindowsProactorEventLoopPolicy is the default in Python 3.8+, but we 
    # ensure it here to support subprocesses (which Selector doesn't).
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    # Monkey patch to silence 'Event loop is closed' errors during shutdown
    from functools import wraps
    from asyncio.proactor_events import _ProactorBasePipeTransport
    
    _orig_del = _ProactorBasePipeTransport.__del__
    @wraps(_orig_del)
    def _patched_del(self):
        try:
            _orig_del(self)
        except RuntimeError as e:
            if str(e) != 'Event loop is closed':
                raise
    _ProactorBasePipeTransport.__del__ = _patched_del

# 2. Add current directory to the path so it can see the 'nanobot' folder
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# ==========================================
# --- 3. CUSTOM CONFIG LOADING & PATCH ---
# ==========================================
RAW_CONFIG = {}

try:
    import nanobot.config.loader
    _orig_migrate = nanobot.config.loader._migrate_config
    
    def _patched_migrate(data):
        # 1. Capture the original data into our global RAW_CONFIG
        global RAW_CONFIG
        RAW_CONFIG = json.loads(json.dumps(data)) # Deep copy for our patches to use
        
        # 2. Run the original migration
        data = _orig_migrate(data)
        
        # 3. Strip our custom keys so Pydantic validation doesn't crash Nanobot
        if "agents" in data:
            agents = data["agents"]
            # Strip agents.consolidator
            agents.pop("consolidator", None)
            
            # Strip agents.defaults.compaction and agents.defaults.contextPruning
            if "defaults" in agents:
                defaults = agents["defaults"]
                defaults.pop("compaction", None)
                defaults.pop("contextPruning", None)
                defaults.pop("memorySearch", None)
            
            # Strip keywords from specialists
            if "specialists" in agents:
                for spec in agents["specialists"].values():
                    if isinstance(spec, dict):
                        spec.pop("keywords", None)
        
        # Strip root-level memory key
        data.pop("memory", None)
        
        print("[Launcher] Custom config keys intercepted and stripped for compatibility.")
        return data
    
    nanobot.config.loader._migrate_config = _patched_migrate
except Exception as e:
    print(f"[Launcher] Warning: Config loader patch failed: {e}")

# Pre-load RAW_CONFIG manually for very early patches (like Heartbeat)
def get_raw_config_manually():
    config_path = Path.home() / ".nanobot" / "config.json"
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: pass
    return {}

if not RAW_CONFIG:
    RAW_CONFIG = get_raw_config_manually()

# ==========================================
# --- 4. PROVIDER LOGGING & ROUTING PATCH ---
# ==========================================
try:
    from loguru import logger
    import litellm
    from nanobot.providers.litellm_provider import LiteLLMProvider
    from nanobot.providers.custom_provider import CustomProvider
    from nanobot.providers.openai_codex_provider import OpenAICodexProvider

    # Patch LiteLLMProvider
    _orig_litellm_chat = LiteLLMProvider.chat
    async def _patched_litellm_chat(self, messages, tools=None, model=None, max_tokens=4096, temperature=0.7):
        target_model = model or self.default_model
        
        # THE OLLAMA BYPASS HAMMER
        if str(target_model).startswith("ollama/"):
            ollama_cfg = RAW_CONFIG.get("providers", {}).get("ollama", {})
            target_base = ollama_cfg.get("apiBase") or "http://localhost:11434/v1"
            target_key = ollama_cfg.get("apiKey") or "ollama"
            
            # LiteLLM's 'ollama' provider expects the base URL (no /v1) 
            # and the bare model name.
            clean_base = target_base
            if "/v1" in clean_base:
                clean_base = clean_base.split("/v1")[0]
            
            clean_model = str(target_model).replace("ollama/", "", 1)
            
            print(f"[Launcher] Bypass Hammer: Forcing Ollama for {clean_model} via {clean_base}")
            
            try:
                # We replicate nanobot's sanitization logic but force the provider
                sanitize_empty = getattr(self, "_sanitize_empty_content", lambda x: x)
                sanitize_msgs = getattr(self, "_sanitize_messages", lambda x: x)
                
                clean_msgs = sanitize_msgs(sanitize_empty(messages))
                
                response = await litellm.acompletion(
                    model=f"ollama/{clean_model}", # LiteLLM still likes the prefix even with custom_llm_provider
                    messages=clean_msgs,
                    tools=tools,
                    api_base=clean_base,
                    api_key=target_key,
                    max_tokens=max(1, max_tokens),
                    temperature=temperature,
                    custom_llm_provider="ollama",
                    drop_params=True
                )
                return self._parse_response(response)
            except Exception as e:
                logger.error("[Launcher] Ollama Bypass Failed: {}", e)
        
        # Standard Logging
        logger.info("[Logging Patch] LiteLLM request: model={}", target_model)
        return await _orig_litellm_chat(self, messages, tools, model, max_tokens, temperature)

    LiteLLMProvider.chat = _patched_litellm_chat
    print("[Launcher] Ollama Bypass Hammer & Logging patches applied.")

    # Patch CustomProvider
    _orig_custom_chat = CustomProvider.chat
    async def _patched_custom_chat(self, *args, **kwargs):
        model = kwargs.get("model") or self.default_model
        logger.info("[Logging Patch] CustomProvider request: model={}", model)
        return await _orig_custom_chat(self, *args, **kwargs)
    CustomProvider.chat = _patched_custom_chat

    # Patch OpenAICodexProvider
    _orig_codex_chat = OpenAICodexProvider.chat
    async def _patched_codex_chat(self, *args, **kwargs):
        model = kwargs.get("model") or self.default_model
        logger.info("[Logging Patch] Codex request: model={}", model)
        return await _orig_codex_chat(self, *args, **kwargs)
    OpenAICodexProvider.chat = _patched_codex_chat

    print("[Launcher] Provider logging patches applied.")
except Exception as e:
    print(f"[Launcher] Warning: Could not apply logging patches. {e}")

# ==========================================
# --- 5. HEARTBEAT MODEL PATCH ---
# ==========================================
try:
    from nanobot.heartbeat.service import HeartbeatService
    
    _orig_hb_init = HeartbeatService.__init__
    def _patched_hb_init(self, *args, **kwargs):
        # The 'model' is usually the 3rd positional argument or in kwargs
        config_model = RAW_CONFIG.get("agents", {}).get("heartbeat", {}).get("model")
        if config_model:
            if len(args) >= 3:
                args = list(args)
                args[2] = config_model # Replace positional model
            else:
                kwargs["model"] = config_model
            print(f"[Launcher] Heartbeat forced to model: {config_model}")
        _orig_hb_init(self, *args, **kwargs)
    
    HeartbeatService.__init__ = _patched_hb_init
except Exception as e:
    print(f"[Launcher] Warning: Could not apply Heartbeat patch. {e}")

# ==========================================
# --- 6. SUBAGENT MCP & SPECIALIST PATCH ---
# ==========================================
try:
    from nanobot.agent.loop import AgentLoop
    import nanobot.agent.subagent
    from nanobot.agent.tools.registry import ToolRegistry
    from nanobot.agent.subagent import SubagentManager
    from nanobot.agent.tools.spawn import SpawnTool

    MAIN_AGENT_TOOLS = None

    # A. Intercept the main AgentLoop to steal its loaded ToolRegistry
    _orig_loop_init = AgentLoop.__init__
    def _patched_loop_init(self, *args, **kwargs):
        _orig_loop_init(self, *args, **kwargs)
        global MAIN_AGENT_TOOLS
        MAIN_AGENT_TOOLS = self.tools
    AgentLoop.__init__ = _patched_loop_init

    # B. Create a proxy ToolRegistry strictly for subagents
    class SubagentToolRegistry(ToolRegistry):
        def get_definitions(self):
            defs = super().get_definitions()
            global MAIN_AGENT_TOOLS
            if MAIN_AGENT_TOOLS:
                # Pass through any MCP tool definitions from the main agent
                main_defs = MAIN_AGENT_TOOLS.get_definitions()
                for d in main_defs:
                    if d.get("function", {}).get("name", "").startswith("mcp_"):
                        defs.append(d)
            return defs

        async def execute(self, name, args):
            global MAIN_AGENT_TOOLS
            # Proxy MCP tool execution to the main agent's active connection stack
            if str(name).startswith("mcp_") and MAIN_AGENT_TOOLS:
                # THE GOOGLE EMAIL HAMMER: Force primary email for Google Workspace tools
                if "google-workspace" in str(name) and isinstance(args, dict):
                    args["user_google_email"] = "allthingscode@gmail.com"
                    print(f"[Launcher] Google Hammer: Forced email to allthingscode@gmail.com for {name}")

                return await MAIN_AGENT_TOOLS.execute(name, args)
            return await super().execute(name, args)

    # Force the subagent module to use our proxy registry
    nanobot.agent.subagent.ToolRegistry = SubagentToolRegistry

    # C. MAIN AGENT TOOL PROXY (For Google Email Hammer)
    _orig_tool_execute = ToolRegistry.execute
    async def _patched_tool_execute(self, name, args):
        # THE GOOGLE EMAIL HAMMER: Force primary email for Google Workspace tools
        if "google-workspace" in str(name) and isinstance(args, dict):
            args["user_google_email"] = "allthingscode@gmail.com"
            print(f"[Launcher] Google Hammer: Forced email to allthingscode@gmail.com for {name}")
        return await _orig_tool_execute(self, name, args)
    ToolRegistry.execute = _patched_tool_execute

    # C. SUBAGENT DEFAULT MODEL PATCH
    _orig_subagent_init = SubagentManager.__init__
    def _patched_subagent_init(self, *args, **kwargs):
        config_model = RAW_CONFIG.get("agents", {}).get("subagent", {}).get("model")
        if config_model:
            # SubagentManager.__init__(self, provider, workspace, bus, model=None, ...)
            # args[0]: provider, args[1]: workspace, args[2]: bus, args[3]: model
            if len(args) >= 4:
                args = list(args)
                args[3] = config_model
            else:
                kwargs["model"] = config_model
            print(f"[Launcher] Subagent default model set from config: {config_model}")
        _orig_subagent_init(self, *args, **kwargs)
    SubagentManager.__init__ = _patched_subagent_init

    # D. MEMORY CONSOLIDATION MODEL PATCH
    try:
        from nanobot.agent.memory import MemoryStore, _SAVE_MEMORY_TOOL
        import json
        _orig_consolidate = MemoryStore.consolidate

        async def _patched_consolidate(self, session, provider, model, **kwargs):
            config_model = RAW_CONFIG.get("agents", {}).get("consolidator", {}).get("model")
            if config_model:
                model = config_model
                print(f"[Launcher] Memory consolidation forced to model: {model}")

            # 1. Prepare messages and prompt (mostly same as original but more explicit)
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
            
            # HARDENED PROMPT for ultra-small models (1.5b/3b)
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
                # We use the provider.chat normally
                response = await provider.chat(
                    messages=[
                        {"role": "system", "content": "You are a JSON-only response agent. You MUST provide valid JSON matching the requested schema. No conversational text."},
                        {"role": "user", "content": prompt},
                    ],
                    tools=_SAVE_MEMORY_TOOL,
                    model=model,
                )

                # 2. Extract Arguments (with Aggressive Text Fallback)
                args = None
                text = response.content or ""
                if response.has_tool_calls:
                    args = response.tool_calls[0].arguments
                    if isinstance(args, str):
                        try: args = json.loads(args)
                        except: pass
                
                if not args or not isinstance(args, dict):
                    # FALLBACK: Aggressive JSON search
                    print(f"[Launcher] Warning: Consolidator failed tool call. Attempting Regex Recovery on: {text[:200]}...")
                    try:
                        import re
                        # 1. Try to find any JSON object
                        match = re.search(r"\{.*\}", text, re.DOTALL)
                        if match:
                            candidate = json.loads(match.group(0))
                            # 2. Map hallucinated keys back to our required schema
                            # Small models often rename keys based on content
                            args = {
                                "history_entry": candidate.get("history_entry") or candidate.get("summary") or candidate.get("subagent_system", {}).get("name") or "No summary available.",
                                "memory_update": candidate.get("memory_update") or candidate.get("facts") or candidate.get("long_term_memory") or current_memory
                            }
                            print("[Launcher] Successfully recovered and remapped consolidation data.")
                    except:
                        pass

                if not args or not isinstance(args, dict):
                    print(f"[Launcher] Memory consolidation FAILED: Model {model} provided no valid data.")
                    return False

                # 3. Apply Updates
                if entry := args.get("history_entry"):
                    self.append_history(str(entry))
                if update := args.get("memory_update"):
                    if update != current_memory:
                        self.write_long_term(str(update))

                session.last_consolidated = 0 if archive_all else len(session.messages) - keep_count
                print(f"[Launcher] Memory consolidation SUCCESSFUL ({len(old_messages)} messages).")
                return True

            except Exception as e:
                print(f"[Launcher] Memory consolidation error: {e}")
                return False

        MemoryStore.consolidate = _patched_consolidate
    except Exception as e:
        print(f"[Launcher] Warning: Could not apply Memory consolidation patch. {e}")

    # G. CONTEXT PRUNING & MEMORY FLUSH PATCH
    try:
        from nanobot.agent.loop import AgentLoop
        from nanobot.bus.events import OutboundMessage
        from datetime import datetime, timedelta

        _orig_process_message = AgentLoop._process_message

        async def _patched_process_message(self, msg, session_key=None, on_progress=None):
            # 1. Context Pruning (Lightweight Cleanup)
            prune_cfg = RAW_CONFIG.get("agents", {}).get("defaults", {}).get("contextPruning", {})
            if prune_cfg.get("enabled"):
                key = session_key or msg.session_key
                session = self.sessions.get_or_create(key)
                ttl_str = prune_cfg.get("ttl", "6h")
                # Simple TTL check (e.g., '6h')
                if ttl_str.endswith("h"):
                    hours = int(ttl_str[:-1])
                    cutoff = datetime.now() - timedelta(hours=hours)
                    # Filter tool results older than TTL, keeping last X assistants
                    new_msgs = []
                    assistant_count = 0
                    for m in reversed(session.messages):
                        role = m.get("role")
                        ts_str = m.get("timestamp")
                        is_old = False
                        if ts_str:
                            try:
                                ts = datetime.fromisoformat(ts_str)
                                if ts < cutoff:
                                    is_old = True
                            except: pass
                        
                        if role == "assistant":
                            assistant_count += 1
                        
                        # Keep if not old, OR if it's one of the last X assistants, OR it's a user message
                        if not is_old or assistant_count <= prune_cfg.get("keepLastAssistants", 3) or role == "user":
                            new_msgs.append(m)
                    
                    if len(new_msgs) < len(session.messages):
                        print(f"[Launcher] Context Pruning: Trimmed {len(session.messages) - len(new_msgs)} old messages.")
                        session.messages = list(reversed(new_msgs))

            # 2. Memory Flush (Early Warning)
            flush_cfg = RAW_CONFIG.get("agents", {}).get("defaults", {}).get("compaction", {}).get("memoryFlush", {})
            if flush_cfg.get("enabled"):
                key = session_key or msg.session_key
                session = self.sessions.get_or_create(key)
                
                # We use unconsolidated message count as a proxy for tokens here 
                # (since exact token counting is expensive/provider-specific)
                unconsolidated = len(session.messages) - session.last_consolidated
                # Guide recommends 40,000 tokens, nanobot's window is usually small (e.g. 50-100 messages)
                # We'll trigger if we are at 80% of the memory window
                if unconsolidated >= (self.memory_window * 0.8):
                    print(f"[Launcher] Memory Flush triggered (unconsolidated: {unconsolidated})")
                    # Run a special "flush" turn
                    flush_prompt = flush_cfg.get("prompt", "Store durable memories now.")
                    sys_prompt = flush_cfg.get("systemPrompt", "Session nearing compaction.")
                    
                    # Temporarily inject flush instruction
                    history = session.get_history(max_messages=self.memory_window)
                    flush_msgs = self.context.build_messages(
                        history=history,
                        current_message=f"### SYSTEM NOTIFICATION: {sys_prompt}\n\n{flush_prompt}",
                        channel=msg.channel, chat_id=msg.chat_id
                    )
                    
                    # Execute flush (ignore tool iterations for simplicity)
                    res, _, all_msgs = await self._run_agent_loop(flush_msgs)
                    if res and res != "NO_REPLY":
                        print(f"[Launcher] Memory Flush captured data.")
                        self._save_turn(session, all_msgs, 1 + len(history))
                    
                    # Force a consolidation immediately after flush
                    await self._consolidate_memory(session)

            return await _orig_process_message(self, msg, session_key, on_progress)

        AgentLoop._process_message = _patched_process_message
        print("[Launcher] Context Pruning & Memory Flush patches applied.")
    except Exception as e:
        print(f"[Launcher] Error applying Pruning/Flush patches: {e}")

    # E. SPECIALIST MODEL ROUTING & SUBAGENT EXECUTION
    # We patch _run_subagent to select the model based on task/label RIGHT BEFORE starting.
    # This avoids the race condition where the model was reset before the task started.
    _orig_run_subagent = SubagentManager._run_subagent
    async def _patched_run_subagent(self, task_id, task, label, origin):
        specialists = RAW_CONFIG.get("agents", {}).get("specialists", {})
        selected_model = None
        
        # Use label if task is too long for keyword matching
        search_text = (label or "") + " " + task
        task_lower = search_text.lower()
        
        # 1. Dynamic keyword matching from config
        for name, spec in specialists.items():
            kws = spec.get("keywords", [])
            if any(kw.lower() in task_lower for kw in kws):
                selected_model = spec.get("model")
                if selected_model:
                    print(f"[Launcher] Subagent [{task_id}] Specialist Match: {name} -> {selected_model}")
                    break
        
        # 2. Hardcoded fallbacks
        if not selected_model:
            if any(kw in task_lower for kw in ["research", "find", "search", "documentation"]):
                if "researcher" in specialists:
                    selected_model = specialists["researcher"].get("model")
                    print(f"[Launcher] Subagent [{task_id}] Specialist: researcher -> {selected_model}")
            elif any(kw in task_lower for kw in ["architect", "design", "structure", "refactor"]):
                if "architect" in specialists:
                    selected_model = specialists["architect"].get("model")
                    print(f"[Launcher] Subagent [{task_id}] Specialist: architect -> {selected_model}")

        # Override self.model for THIS execution
        original_instance_model = self.model
        if selected_model:
            self.model = selected_model
        
        try:
            return await _orig_run_subagent(self, task_id, task, label, origin)
        finally:
            self.model = original_instance_model
            
    SubagentManager._run_subagent = _patched_run_subagent

    # F. Inject the instruction into the subagent's system prompt
    _orig_build_prompt = SubagentManager._build_subagent_prompt
    def _patched_build_prompt(self, task):
        prompt = _orig_build_prompt(self, task)
        prompt += (
            "\n\n## CRITICAL OVERRIDE\n"
            "You have access to advanced MCP tools (e.g., 'mcp_google-ai-search_search_ai'). "
            "You MUST prioritize these tools over the basic web_search whenever possible."
        )
        return prompt
    SubagentManager._build_subagent_prompt = _patched_build_prompt

    print("[Launcher] Subagent MCP & Specialist patches applied.")
except Exception as e:
    print(f"[Launcher] Error applying Subagent patches: {e}")
# ==========================================

# ==========================================
# --- 7. PRE-START CLEANUP (Sanity Check) ---
# ==========================================
def pre_start_cleanup():
    """Clear stale MCP state or temporary auth files to prevent 'Missing code verifier' errors."""
    try:
        # 1. Clear common temporary auth files for Google MCP
        mcp_dir = Path.home() / ".google_workspace_mcp"
        if mcp_dir.exists():
            # We DON'T delete the 'credentials' folder (which has tokens), 
            # but we delete any temporary JSON files or pickles outside of it.
            for item in mcp_dir.glob("*.json"):
                if "credentials" not in str(item):
                    item.unlink()
                    print(f"[Launcher] Cleaned up stale auth state: {item.name}")
        
        # 2. Clear common workspace temp files
        workspace_dir = Path.home() / ".nanobot" / "workspace"
        if workspace_dir.exists():
            for item in workspace_dir.glob("*.tmp"):
                item.unlink()
    except Exception as e:
        print(f"[Launcher] Warning: Pre-start cleanup skipped: {e}")

if __name__ == "__main__":
    # Execute cleanup before starting
    pre_start_cleanup()

    # Mimic the CLI arguments: 'nanobot gateway'
    sys.argv = ["nanobot", "gateway"]
    
    print(f"[Launcher] Starting nanobot with Windows fix...")
    
    try:
        runpy.run_module("nanobot", run_name="__main__", alter_sys=True)
    except KeyboardInterrupt:
        print("\n[Launcher] Shutdown signal received. Closing gracefully...")
        sys.exit(0)
    except Exception as e:
        print(f"\n[Launcher] Caught error: {e}")
        sys.exit(1)
