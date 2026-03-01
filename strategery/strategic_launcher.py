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
        from nanobot.channels.telegram import TelegramChannel, _split_message, _markdown_to_telegram_html
        from nanobot.bus.events import OutboundMessage
        from telegram import ReplyParameters

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

                # STRATEGIC EDITION: Handle Telegram Topics (threads)
                if update.message and hasattr(update.message, 'message_thread_id') and update.message.message_thread_id:
                    msg = update.message
                    orig_hm = self._handle_message
                    async def temp_hm(*args, **kwargs):
                        chat_id = kwargs.get("chat_id") or (args[1] if len(args) > 1 else None)
                        metadata = dict(kwargs.get("metadata") or (args[4] if len(args) > 4 else {}))
                        metadata["message_thread_id"] = msg.message_thread_id
                        # Force session key to be thread-specific
                        metadata["session_key_override"] = f"telegram:{chat_id}:{msg.message_thread_id}"
                        kwargs["metadata"] = metadata
                        kwargs["session_key"] = metadata["session_key_override"]
                        return await orig_hm(*args, **kwargs)
                    self._handle_message = temp_hm
                    try:
                        return await self._orig_on_message_strategic(update, context)
                    finally:
                        self._handle_message = orig_hm

                return await self._orig_on_message_strategic(update, context)
            TelegramChannel._on_message = _strategic_on_message

        # Complete rewrite of send to handle message_thread_id WITHOUT monkey-patching bot
        async def _thread_aware_send(self, msg: OutboundMessage) -> None:
            if not self._app: return
            self._stop_typing(msg.chat_id)
            try: chat_id = int(msg.chat_id)
            except: return

            thread_id = msg.metadata.get("message_thread_id")
            reply_params = None
            if self.config.reply_to_message:
                if reply_to_id := msg.metadata.get("message_id"):
                    reply_params = ReplyParameters(message_id=reply_to_id, allow_sending_without_reply=True)

            # Send media
            for media_path in (msg.media or []):
                try:
                    from nanobot.channels.telegram import _get_media_type
                    mtype = _get_media_type(media_path)
                    sender = {"photo": self._app.bot.send_photo, "voice": self._app.bot.send_voice, "audio": self._app.bot.send_audio}.get(mtype, self._app.bot.send_document)
                    param = "photo" if mtype == "photo" else mtype if mtype in ("voice", "audio") else "document"
                    with open(media_path, 'rb') as f:
                        kwargs = {param: f, "chat_id": chat_id, "reply_parameters": reply_params}
                        if thread_id: kwargs["message_thread_id"] = int(thread_id)
                        await sender(**kwargs)
                except Exception as e:
                    logger.error("Failed to send media: {}", e)

            # Send text
            if msg.content and msg.content != "[empty message]":
                for chunk in _split_message(msg.content):
                    try:
                        html = _markdown_to_telegram_html(chunk)
                        kwargs = {"chat_id": chat_id, "text": html, "parse_mode": "HTML", "reply_parameters": reply_params}
                        if thread_id: kwargs["message_thread_id"] = int(thread_id)
                        await self._app.bot.send_message(**kwargs)
                    except Exception as e:
                        kwargs = {"chat_id": chat_id, "text": chunk, "reply_parameters": reply_params}
                        if thread_id: kwargs["message_thread_id"] = int(thread_id)
                        await self._app.bot.send_message(**kwargs)

        TelegramChannel.send = _thread_aware_send

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
            
            try:
                # STRATEGIC FIX: We no longer dynamically patch ToolRegistry.__init__ here.
                # Dynamic global patching in an async context is unsafe and leads to 
                # 'maximum recursion depth exceeded' when concurrent subagents are spawned.
                return await self._orig_run_subagent_strategic(task_id, task, label, origin)
            finally:
                self.model = orig_model

        SubagentManager._run_subagent = _patched_run_subagent

    if not hasattr(SubagentManager, "_orig_build_prompt_strategic"):
        SubagentManager._orig_build_prompt_strategic = SubagentManager._build_subagent_prompt
        def _patched_build_prompt(self):
            reset_instr = """

## CRITICAL OVERRIDE & DESIGN MANDATES
1. **Tool Naming:** You MUST use the exact, full name for all tools as provided in your tool list. For MCP tools, this ALWAYS includes the `mcp_` prefix (e.g., `mcp_email-reporter_send_email_report`). Do NOT abbreviate or strip the namespace.
2. **Tool Deprecation:** The standard `mcp_google-workspace_` tools are DEPRECATED. They are unstable and do not target the correct mailbox. DO NOT use them.
3. **Surgical Tools:** Use ONLY `mcp_google-surgical_` tools for Tasks and Calendar. Use `mcp_email-reporter_` for all outbound briefings. These custom wrappers provide precision and use the correct user credentials.
4. **Prioritize Advanced Search:** Always prioritize `mcp_google-ai-search` over the base `web_search`.
5. **Specialist Selection:** If you have been assigned to this task with `gemini-1.5-pro` (check the logs if available), it is because this task requires high-depth reasoning (Research, Architecture, or Planning). Focus on thoroughness.
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
        mcp_dir = Path.home() / ".google_workspace_mcp"
        if mcp_dir.exists():
            # Clear only session-level JSON files, NOT the credentials folder
            for item in mcp_dir.glob("*.json"):
                if "credentials" not in str(item): item.unlink()

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
