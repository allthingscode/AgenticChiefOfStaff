import asyncio
import sys
import runpy
import os
import json
from pathlib import Path

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
# --- 3. CUSTOM CONFIG LOADING ---
# ==========================================
def load_raw_config():
    config_path = Path.home() / ".nanobot" / "config.json"
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}

RAW_CONFIG = load_raw_config()

# ==========================================
# --- 4. PROVIDER LOGGING PATCH ---
# ==========================================
try:
    from loguru import logger
    from nanobot.providers.litellm_provider import LiteLLMProvider
    from nanobot.providers.custom_provider import CustomProvider
    from nanobot.providers.openai_codex_provider import OpenAICodexProvider

    # Patch LiteLLMProvider
    _orig_litellm_chat = LiteLLMProvider.chat
    async def _patched_litellm_chat(self, *args, **kwargs):
        model = kwargs.get("model") or self.default_model
        logger.info("[Logging Patch] LiteLLM request: model={}", model)
        return await _orig_litellm_chat(self, *args, **kwargs)
    LiteLLMProvider.chat = _patched_litellm_chat

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
                return await MAIN_AGENT_TOOLS.execute(name, args)
            return await super().execute(name, args)

    # Force the subagent module to use our proxy registry
    nanobot.agent.subagent.ToolRegistry = SubagentToolRegistry

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
        from nanobot.agent.memory import MemoryStore
        _orig_consolidate = MemoryStore.consolidate
        async def _patched_consolidate(self, session, provider, model, **kwargs):
            config_model = RAW_CONFIG.get("agents", {}).get("consolidator", {}).get("model")
            if config_model:
                model = config_model
                print(f"[Launcher] Memory consolidation forced to model: {config_model}")
            return await _orig_consolidate(self, session, provider, model, **kwargs)
        MemoryStore.consolidate = _patched_consolidate
    except Exception as e:
        print(f"[Launcher] Warning: Could not apply Memory consolidation patch. {e}")

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

if __name__ == "__main__":
    # 7. Mimic the CLI arguments: 'nanobot gateway'
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
