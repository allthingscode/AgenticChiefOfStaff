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

# Detect config path
def get_hayes_config():
    # Priority: System config, local fallback
    home_config = Path.home() / ".nanobot" / "config.json"
    if home_config.exists():
        with open(home_config, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

HAYES_CONFIG = get_hayes_config()
STRATEGIC = HAYES_CONFIG.get("hayes_strategic", {})
USER_EMAIL = STRATEGIC.get("user_email", "admin@example.com")
STORAGE_ROOT = Path(STRATEGIC.get("storage_root", "D:/Nanobot_Storage"))

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
            # Strip custom strategic keys
            data.pop("hayes_strategic", None)
            
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
if not RAW_CONFIG:
    RAW_CONFIG = HAYES_CONFIG

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
    async def _patched_litellm_chat(self, messages, tools=None, model=None, max_tokens=4096, temperature=0.7, reasoning_effort=None, **kwargs):
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
                
                # Create LiteLLM completion
                acompletion_kwargs = {
                    "model": f"ollama/{clean_model}",
                    "messages": clean_msgs,
                    "tools": tools,
                    "api_base": clean_base,
                    "api_key": target_key,
                    "max_tokens": max(1, max_tokens),
                    "temperature": temperature,
                    "custom_llm_provider": "ollama",
                    "drop_params": True
                }
                if reasoning_effort:
                    acompletion_kwargs["reasoning_effort"] = reasoning_effort

                response = await litellm.acompletion(**acompletion_kwargs)
                return self._parse_response(response)
            except Exception as e:
                logger.error("[Launcher] Ollama Bypass Failed: {}", e)
        
        # Standard Logging
        logger.info("[Logging Patch] LiteLLM request: model={}", target_model)
        return await _orig_litellm_chat(self, messages, tools=tools, model=model, max_tokens=max_tokens, temperature=temperature, reasoning_effort=reasoning_effort, **kwargs)

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

    # A. SUBAGENT DEFAULT MODEL PATCH
    _orig_subagent_init = SubagentManager.__init__
    def _patched_subagent_init(self, *args, **kwargs):
        config_model = RAW_CONFIG.get("agents", {}).get("subagent", {}).get("model")
        if config_model:
            # SubagentManager.__init__(self, provider, workspace, bus, model=None, ...)
            if len(args) >= 4:
                args = list(args)
                args[3] = config_model
            else:
                kwargs["model"] = config_model
            print(f"[Launcher] Subagent default model set from config: {config_model}")
        _orig_subagent_init(self, *args, **kwargs)
    SubagentManager.__init__ = _patched_subagent_init

    # B. MAIN AGENT TOOL PROXY (For Google Email Hammer)
    _orig_tool_execute = ToolRegistry.execute
    async def _patched_tool_execute(self, name, args):
        # THE GOOGLE EMAIL HAMMER: Force primary email for Google Surgical tools
        if "google-surgical" in str(name) and isinstance(args, dict):
            # Intercept both 'user_google_email' and 'email' parameters
            if "user_google_email" in args:
                args["user_google_email"] = USER_EMAIL
            if "email" in args:
                args["email"] = USER_EMAIL
            print(f"[Launcher] Google Hammer: Forced email to {USER_EMAIL} for {name}")
        return await _orig_tool_execute(self, name, args)
    ToolRegistry.execute = _patched_tool_execute

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

        _orig_process_message = AgentLoop._process_message

        async def _patched_process_message(self, msg, session_key=None, on_progress=None):
            # 1. Context Pruning
            prune_cfg = RAW_CONFIG.get("agents", {}).get("defaults", {}).get("contextPruning", {})
            if prune_cfg.get("enabled"):
                key = session_key or msg.session_key
                session = self.sessions.get_or_create(key)
                ttl_str = prune_cfg.get("ttl", "6h")
                if ttl_str.endswith("h"):
                    hours = int(ttl_str[:-1])
                    cutoff = datetime.now() - timedelta(hours=hours)
                    new_msgs = []
                    assistant_count = 0
                    for m in reversed(session.messages):
                        role = m.get("role")
                        ts_str = m.get("timestamp")
                        is_old = False
                        if ts_str:
                            try:
                                if datetime.fromisoformat(ts_str) < cutoff:
                                    is_old = True
                            except: pass
                        if role == "assistant": assistant_count += 1
                        if not is_old or assistant_count <= prune_cfg.get("keepLastAssistants", 3) or role == "user":
                            new_msgs.append(m)
                    if len(new_msgs) < len(session.messages):
                        session.messages = list(reversed(new_msgs))

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

            return await _orig_process_message(self, msg, session_key, on_progress)

        AgentLoop._process_message = _patched_process_message
        print("[Launcher] Context Pruning & Memory Flush patches applied.")
    except Exception as e:
        print(f"[Launcher] Error applying Pruning/Flush patches: {e}")

    # H. TELEGRAM TOPICS (THREADS) PATCH
    try:
        from nanobot.channels.telegram import TelegramChannel, _split_message, _markdown_to_telegram_html
        from nanobot.bus.events import OutboundMessage, InboundMessage
        from telegram import ReplyParameters

        # 1. Intercept incoming messages
        _orig_on_message = TelegramChannel._on_message
        async def _patched_on_message(self, update, context):
            # --- HAYES MEDIA REDIRECTION PATCH ---
            # Monkey-patch the download_to_drive method of the file object before it's called
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
                                from nanobot.utils.helpers import ensure_dir
                                # Re-route to D:\Nanobot_Storage\media via the workspace config
                                workspace = Path(getattr(self.config, "workspace_path", Path.home() / ".nanobot" / "workspace"))
                                media_dir = ensure_dir(workspace / "media")
                                filename = Path(custom_path).name
                                custom_path = str(media_dir / filename)
                                print(f"[Launcher] Telegram Media Redirection: {custom_path}")
                            return await _orig_download(custom_path=custom_path, *args, **kwargs)
                        file.download_to_drive = _patched_download
                        return file
                    context.bot.get_file = _patched_get_file

            if update.message and hasattr(update.message, 'message_thread_id') and update.message.message_thread_id:
                msg = update.message
                orig_hm = self._handle_message
                async def temp_hm(*args, **kwargs):
                    chat_id = kwargs.get("chat_id") or (args[1] if len(args) > 1 else None)
                    metadata = dict(kwargs.get("metadata") or (args[4] if len(args) > 4 else {}))
                    metadata["message_thread_id"] = msg.message_thread_id
                    metadata["session_key_override"] = f"telegram:{chat_id}:{msg.message_thread_id}"
                    kwargs["metadata"] = metadata
                    kwargs["session_key"] = metadata["session_key_override"]
                    return await orig_hm(*args, **kwargs)
                self._handle_message = temp_hm
                try:
                    return await _orig_on_message(self, update, context)
                finally:
                    self._handle_message = orig_hm
            return await _orig_on_message(self, update, context)
        TelegramChannel._on_message = _patched_on_message

        # 2. Complete rewrite of send to handle message_thread_id WITHOUT monkey-patching bot
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
                    mtype = self._get_media_type(media_path)
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
        print("[Launcher] Telegram Topics (Threads) support enabled.")
    except Exception as e:
        print(f"[Launcher] Error applying Telegram Topics patch: {e}")

    # I. SPECIALIST MODEL ROUTING
    _orig_run_subagent = SubagentManager._run_subagent
    async def _patched_run_subagent(self, task_id, task, label, origin):
        specialists = RAW_CONFIG.get("agents", {}).get("specialists", {})
        selected_model = None
        task_lower = ((label or "") + " " + task).lower()
        for name, spec in specialists.items():
            if any(kw.lower() in task_lower for kw in spec.get("keywords", [])):
                selected_model = spec.get("model")
                if selected_model: break
        if not selected_model:
            if any(kw in task_lower for kw in ["research", "find", "search"]):
                selected_model = specialists.get("researcher", {}).get("model")
            elif any(kw in task_lower for kw in ["architect", "design", "structure"]):
                selected_model = specialists.get("architect", {}).get("model")
        orig_model = self.model
        if selected_model: self.model = selected_model
        try: return await _orig_run_subagent(self, task_id, task, label, origin)
        finally: self.model = orig_model
    SubagentManager._run_subagent = _patched_run_subagent

    _orig_build_prompt = SubagentManager._build_subagent_prompt
    def _patched_build_prompt(self):
        reset_instr = """

## CRITICAL OVERRIDE & DESIGN MANDATES
1. **Tool Deprecation:** The standard `mcp_google-workspace_` tools are DEPRECATED. They are unstable and do not target the correct mailbox. DO NOT use them.
2. **Surgical Tools:** Use ONLY `mcp_google-surgical_` tools for Tasks and Calendar. Use `mcp_email-reporter_` for all outbound briefings. These custom wrappers provide precision and use the correct user credentials.
3. **Prioritize Advanced Search:** Always prioritize `mcp_google-ai-search` over the base `web_search`.
4. **Specialist Selection:** If you have been assigned to this task with `gemini-1.5-pro` (check the logs if available), it is because this task requires high-depth reasoning (Research, Architecture, or Planning). Focus on thoroughness.
"""
        return _orig_build_prompt(self) + reset_instr
    SubagentManager._build_subagent_prompt = _patched_build_prompt
    print("[Launcher] Subagent MCP & Specialist patches applied.")
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
    print(f"[Launcher] Starting nanobot with Windows fix...")
    try:
        runpy.run_module("nanobot", run_name="__main__", alter_sys=True)
    except KeyboardInterrupt: sys.exit(0)
    except Exception as e:
        print(f"\n[Launcher] Caught error: {e}")
        sys.exit(1)
