import asyncio
import sys
import runpy
import os
import json
import io
from pathlib import Path

# Force UTF-8 encoding for Windows stdout/stderr to prevent charmap errors
if sys.platform == 'win32' and __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    # Also force UTF-8 for the entire process environment
    os.environ["PYTHONIOENCODING"] = "utf-8"
    os.environ["PYTHONUTF8"] = "1"

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
        except (RuntimeError, ValueError) as e:
            # Silence common Windows shutdown noise
            _msg = str(e)
            if 'Event loop is closed' in _msg or 'I/O operation on closed pipe' in _msg:
                pass
            else:
                raise
    _ProactorBasePipeTransport.__del__ = _patched_del

# 2. Add project root to the path so it can see the 'nanobot' folder
# The project root is one level up from the 'strategery' folder where this script is located.
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# CRITICAL: Apply config loader patch immediately to support all tools
try:
    import nanobot.config.loader
    from nanobot.config.schema import Config
    
    # Force the Config schema to ignore extra fields at runtime
    Config.model_config["extra"] = "ignore"
    
    if not hasattr(nanobot.config.loader, "_orig_load_config_strategic"):
        nanobot.config.loader._orig_load_config_strategic = nanobot.config.loader.load_config
        def _strategic_load_config(config_path=None):
            path = config_path or nanobot.config.loader.get_config_path()
            if path.exists():
                try:
                    with open(path, "r", encoding="utf-8-sig") as f:
                        data = json.load(f)
                    # We must also patch _migrate_config because load_config calls it
                    return Config.model_validate(nanobot.config.loader._migrate_config(data))
                except Exception as e:
                    print(f"[Launcher] Warning: Failed to load config: {e}")
            return Config()
        nanobot.config.loader.load_config = _strategic_load_config

    if not hasattr(nanobot.config.loader, "_orig_migrate_strategic"):
        nanobot.config.loader._orig_migrate_strategic = nanobot.config.loader._migrate_config
        def _patched_migrate(data):
            # 1. Capture the original data into our global RAW_CONFIG
            global RAW_CONFIG
            RAW_CONFIG = json.loads(json.dumps(data)) # Deep copy for our patches to use
            
            # 2. Run the original migration
            data = nanobot.config.loader._orig_migrate_strategic(data)
            
            # 3. Strip our custom keys so Pydantic validation doesn't crash Nanobot
            if "agents" in data:
                agents = data["agents"]
                data.pop("strategic_edition", None)
                agents.pop("consolidator", None)
                if "defaults" in agents:
                    defaults = agents["defaults"]
                    defaults.pop("compaction", None)
                    defaults.pop("contextPruning", None)
                    defaults.pop("memorySearch", None)
                if "specialists" in agents:
                    for spec in agents["specialists"].values():
                        if isinstance(spec, dict): spec.pop("keywords", None)
            data.pop("memory", None)
            return data
        nanobot.config.loader._migrate_config = _patched_migrate
        print("[Launcher] Global config patches applied.")
except Exception as e:
    print(f"[Launcher] Warning: Config loader patch failed: {e}")

# ==========================================
# --- 3. CUSTOM CONFIG LOADING ---
# ==========================================
RAW_CONFIG = {}
USER_EMAIL = "admin@example.com"
STORAGE_ROOT = Path.home() / ".nanobot" / "storage"

try:
    # Priority: System config, local fallback
    home_config = Path.home() / ".nanobot" / "config.json"
    if home_config.exists():
        with open(home_config, "r", encoding="utf-8-sig") as f:
            _raw = json.load(f)
            RAW_CONFIG = _raw
            _strat = _raw.get("strategic_edition", {})
            USER_EMAIL = _strat.get("user_email", USER_EMAIL)
            if _s_root := _strat.get("storage_root"):
                STORAGE_ROOT = Path(_s_root)
except: pass

# ==========================================
# --- 4. PROVIDER LOGGING & ROUTING PATCH ---
# ==========================================
try:
    from loguru import logger
    from nanobot.providers.litellm_provider import LiteLLMProvider
    from nanobot.providers.custom_provider import CustomProvider
    from nanobot.providers.openai_codex_provider import OpenAICodexProvider

    # Patch LiteLLMProvider for simple logging
    if not hasattr(LiteLLMProvider, "_orig_chat_strategic"):
        LiteLLMProvider._orig_chat_strategic = LiteLLMProvider.chat
        async def _patched_litellm_chat(self, messages, tools=None, model=None, max_tokens=4096, temperature=0.7, reasoning_effort=None, **kwargs):
            target_model = model or self.default_model
            logger.info("[Strategic] LiteLLM request: model={}", target_model)
            return await self._orig_chat_strategic(messages, tools=tools, model=model, max_tokens=max_tokens, temperature=temperature, reasoning_effort=reasoning_effort, **kwargs)
        LiteLLMProvider.chat = _patched_litellm_chat

    # Patch CustomProvider
    if not hasattr(CustomProvider, "_orig_chat_strategic"):
        CustomProvider._orig_chat_strategic = CustomProvider.chat
        async def _patched_custom_chat(self, *args, **kwargs):
            model = kwargs.get("model") or self.default_model
            logger.info("[Strategic] CustomProvider request: model={}", model)
            return await self._orig_chat_strategic(*args, **kwargs)
        CustomProvider.chat = _patched_custom_chat

    # Patch OpenAICodexProvider
    if not hasattr(OpenAICodexProvider, "_orig_chat_strategic"):
        OpenAICodexProvider._orig_chat_strategic = OpenAICodexProvider.chat
        async def _patched_codex_chat(self, *args, **kwargs):
            model = kwargs.get("model") or self.default_model
            logger.info("[Strategic] Codex request: model={}", model)
            return await self._orig_chat_strategic(*args, **kwargs)
        OpenAICodexProvider.chat = _patched_codex_chat

    print("[Launcher] Provider logging patches applied.")
except Exception as e:
    print(f"[Launcher] Warning: Could not apply logging patches. {e}")

# ==========================================
# --- 5. HEARTBEAT MODEL PATCH ---
# ==========================================
try:
    from nanobot.heartbeat.service import HeartbeatService
    
    if not hasattr(HeartbeatService, "_orig_hb_init_strategic"):
        HeartbeatService._orig_hb_init_strategic = HeartbeatService.__init__
        def _patched_hb_init(self, *args, **kwargs):
            config_model = RAW_CONFIG.get("agents", {}).get("heartbeat", {}).get("model")
            if config_model:
                if len(args) >= 2:
                    args = list(args)
                    args[1] = config_model
                else:
                    kwargs["model"] = config_model
                print(f"[Launcher] Heartbeat forced to model: {config_model}")
            self._orig_hb_init_strategic(*args, **kwargs)
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
    from nanobot.config.schema import MCPServerConfig

    # A. SUBAGENT DEFAULT MODEL PATCH
    if not hasattr(SubagentManager, "_orig_subagent_init_strategic"):
        SubagentManager._orig_subagent_init_strategic = SubagentManager.__init__
        def _patched_subagent_init(self, *args, **kwargs):
            config_model = RAW_CONFIG.get("agents", {}).get("subagent", {}).get("model")
            if config_model:
                if len(args) >= 4:
                    args = list(args)
                    args[3] = config_model
                else:
                    kwargs["model"] = config_model
            current_model = kwargs.get('model') or (args[3] if len(args) > 3 else 'auto')
            print(f"[Strategic] SubagentManager initialized (Model: {current_model})")
            
            # Store MCP server config for subagents
            mcp_data = RAW_CONFIG.get("tools", {}).get("mcpServers", {})
            self._mcp_configs = {k: MCPServerConfig.model_validate(v) for k, v in mcp_data.items()}
            
            self._orig_subagent_init_strategic(*args, **kwargs)
        SubagentManager.__init__ = _patched_subagent_init

    # B. MAIN AGENT TOOL PROXY
    if not hasattr(ToolRegistry, "_orig_tool_execute_strategic"):
        ToolRegistry._orig_tool_execute_strategic = ToolRegistry.execute
        async def _patched_tool_execute(self, name, args):
            if "google-surgical" in str(name) and isinstance(args, dict):
                if "user_google_email" in args: args["user_google_email"] = USER_EMAIL
                if "email" in args: args["email"] = USER_EMAIL
                print(f"[Launcher] Google Hammer: {USER_EMAIL}")
            
            if name == "exec" and sys.platform == "win32" and isinstance(args, dict):
                cmd = args.get("command", "").strip().lower()
                if cmd == "date": args["command"] = "date /t"
                elif cmd == "time": args["command"] = "time /t"
            
            if name == "web_search":
                return "ERROR: The 'web_search' tool is DEPRECATED and disabled. You MUST use 'mcp_google-ai-search_search_ai' instead."

            return await self._orig_tool_execute_strategic(name, args)
        ToolRegistry.execute = _patched_tool_execute

    # D. MEMORY CONSOLIDATION MODEL PATCH
    try:
        from nanobot.agent.memory import MemoryStore, _SAVE_MEMORY_TOOL
        import json
        if not hasattr(MemoryStore, "_orig_consolidate_strategic"):
            MemoryStore._orig_consolidate_strategic = MemoryStore.consolidate

            async def _patched_consolidate(self, session, provider, model, **kwargs):
                config_model = RAW_CONFIG.get("agents", {}).get("consolidator", {}).get("model")
                if config_model:
                    model = config_model
                    print(f"[Launcher] Memory consolidation forced to model: {model}")

                return await self._orig_consolidate_strategic(session, provider, model, **kwargs)

            MemoryStore.consolidate = _patched_consolidate
    except Exception as e:
        print(f"[Launcher] Warning: Could not apply Memory consolidation patch. {e}")

    # G. CONTEXT PRUNING & MEMORY FLUSH PATCH
    try:
        from nanobot.agent.loop import AgentLoop
        from nanobot.bus.events import OutboundMessage
        from datetime import datetime, timedelta

        if not hasattr(AgentLoop, "_orig_process_message_strategic"):
            AgentLoop._orig_process_message_strategic = AgentLoop._process_message

            async def _patched_process_message(self, msg, session_key=None, on_progress=None):
                # 1. Context Pruning
                prune_cfg = RAW_CONFIG.get("agents", {}).get("defaults", {}).get("contextPruning", {})
                if prune_cfg.get("enabled"):
                    key = session_key or msg.session_key
                    session = self.sessions.get_or_create(key)
                    ttl_str = prune_cfg.get("ttl", "6h")
                    hours = int(ttl_str[:-1]) if ttl_str.endswith("h") else 6
                    cutoff = datetime.now() - timedelta(hours=hours)
                    
                    new_msgs = []
                    assistant_count = 0
                    needed_tool_ids = set()
                    
                    # Pass 1: Identification (Reverse to find newest first)
                    for m in reversed(session.messages):
                        role = m.get("role")
                        
                        # Cache/parse timestamp
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
                                # If we keep an assistant call with tools, we MUST keep the responses
                                for tc in (m.get("tool_calls") or []):
                                    if tid := tc.get("id"): needed_tool_ids.add(tid)
                        elif role == "tool":
                            # We'll decide in Pass 2 based on needed_tool_ids
                            pass
                        
                        if keep:
                            new_msgs.append(m)
                    
                    # Pass 2: Tool Resolution (Forward to maintain order)
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
                flush_cfg = RAW_CONFIG.get("agents", {}).get("defaults", {}).get("compaction", {}).get("memoryFlush", {})
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
                            current_message=f"### SYSTEM NOTIFICATION: {sys_prompt}\n\n{flush_prompt}",
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
    except Exception as e:
        print(f"[Launcher] Error applying Pruning/Flush patches: {e}")

    # H. TELEGRAM PATCHES
    try:
        from nanobot.channels.telegram import TelegramChannel
        if not hasattr(TelegramChannel, "_orig_on_message_strategic"):
            TelegramChannel._orig_on_message_strategic = TelegramChannel._on_message
            async def _strategic_on_message(self, update, context):
                if update.message:
                    media_file = None
                    if update.message.photo: media_file = update.message.photo[-1]
                    elif update.message.voice: media_file = update.message.voice
                    elif update.message.audio: media_file = update.message.audio
                    elif update.message.document: media_file = update.message.document
                    
                    if media_file:
                        _orig_get_file = context.bot.get_file
                        async def _patched_get_file(file_id, *args, **kwargs):
                            file = await _orig_get_file(file_id, *args, **kwargs)
                            _orig_download = file.download_to_drive
                            async def _patched_download(custom_path=None, *args, **kwargs):
                                if custom_path and ".nanobot\\media" in str(custom_path):
                                    workspace = Path(getattr(self.config, "workspace_path", Path.home() / ".nanobot" / "workspace"))
                                    custom_path = str(workspace / "media" / Path(custom_path).name)
                                    print(f"[Launcher] Telegram Media Redirection: {custom_path}")
                                return await _orig_download(custom_path=custom_path, *args, **kwargs)
                            file.download_to_drive = _patched_download
                            return file
                        context.bot.get_file = _patched_get_file
                return await self._orig_on_message_strategic(update, context)
            TelegramChannel._on_message = _strategic_on_message
    except Exception as e:
        print(f"[Launcher] Error applying Telegram patches: {e}")

    # I. SPECIALIST MODEL ROUTING & MCP FOR SUBAGENTS
    if not hasattr(SubagentManager, "_orig_run_subagent_strategic"):
        SubagentManager._orig_run_subagent_strategic = SubagentManager._run_subagent
        async def _patched_run_subagent(self, task_id, task, label, origin):
            specialists = RAW_CONFIG.get("agents", {}).get("specialists", {})
            selected_model = None
            task_lower = ((label or "") + " " + task).lower()
            for name, spec in specialists.items():
                if any(kw.lower() in task_lower for kw in spec.get("keywords", [])):
                    selected_model = spec.get("model"); break
            if not selected_model:
                if any(kw in task_lower for kw in ["research", "find", "search"]): selected_model = specialists.get("researcher", {}).get("model")
                elif any(kw in task_lower for kw in ["architect", "design", "structure"]): selected_model = specialists.get("architect", {}).get("model")
            
            orig_model = self.model
            if selected_model: 
                self.model = selected_model
                print(f"[Strategic] Specialist Router: Assigned {selected_model} for task '{label}'")
            
            from contextlib import AsyncExitStack
            from nanobot.agent.tools.mcp import connect_mcp_servers
            
            async with AsyncExitStack() as stack:
                _orig_reg_init = nanobot.agent.tools.registry.ToolRegistry.__init__
                mcp_connected = False
                
                def _patched_reg_init(reg_self, *args, **kwargs):
                    _orig_reg_init(reg_self, *args, **kwargs)
                    nonlocal mcp_connected
                    if not mcp_connected and hasattr(self, "_mcp_configs"):
                        mcp_connected = True
                        print(f"[Strategic] Subagent [{task_id}] connecting to MCP servers...")
                        # We are in a sync constructor, but connect_mcp_servers is async.
                        # Since this is run inside _run_subagent which IS an async function,
                        # and we want to wait for MCP before the loop starts, we can
                        # just call it in the caller or use a better hook.
                        # For now, let's try to just await it in the caller.
                        pass

                nanobot.agent.tools.registry.ToolRegistry.__init__ = _patched_reg_init
                try:
                    # Instead of patching __init__ to do async work, we'll patch the caller 
                    # or just manually inject after the registry is created.
                    # Let's try a different approach: patch the LLM provider's chat
                    # to connect MCP once before the first call.
                    
                    return await self._orig_run_subagent_strategic(task_id, task, label, origin)
                finally:
                    nanobot.agent.tools.registry.ToolRegistry.__init__ = _orig_reg_init
                    self.model = orig_model

        SubagentManager._run_subagent = _patched_run_subagent

    if not hasattr(SubagentManager, "_orig_build_prompt_strategic"):
        SubagentManager._orig_build_prompt_strategic = SubagentManager._build_subagent_prompt
        def _patched_build_prompt(self):
            reset_instr = """

## CRITICAL OVERRIDE & DESIGN MANDATES
1. **Tool Deprecation:** The standard `mcp_google-workspace_` tools are DEPRECATED. They are unstable and do not target the correct mailbox. DO NOT use them.
2. **Surgical Tools:** Use ONLY `mcp_google-surgical_` tools for Tasks and Calendar. Use `mcp_email-reporter_` for all outbound briefings. These custom wrappers provide precision and use the correct user credentials.
3. **Prioritize Advanced Search:** Always prioritize `mcp_google-ai-search` over the base `web_search`.
4. **Specialist Selection:** If you have been assigned to this task with `gemini-1.5-pro` (check the logs if available), it is because this task requires high-depth reasoning (Research, Architecture, or Planning). Focus on thoroughness.
"""
            return self._orig_build_prompt_strategic() + reset_instr
        SubagentManager._build_subagent_prompt = _patched_build_prompt
    
    print("[Launcher] Subagent & Specialist patches applied.")
except Exception as e:
    print(f"[Launcher] Error applying Subagent patches: {e}")

# ==========================================
# --- 7. PRE-START CLEANUP ---
# ==========================================
def pre_start_cleanup():
    try:
        workspace_dir = Path.home() / ".nanobot" / "workspace"
        if workspace_dir.exists():
            for item in workspace_dir.glob("*.tmp"): item.unlink()
    except: pass

if __name__ == "__main__":
    pre_start_cleanup()
    sys.argv = ["nanobot", "gateway"]
    print(f"[Launcher] Starting nanobot Gateway...")
    try:
        runpy.run_module("nanobot", run_name="__main__", alter_sys=True)
    except KeyboardInterrupt: sys.exit(0)
    except Exception as e:
        print(f"\n[Launcher] Fatal: {e}")
        sys.exit(1)
