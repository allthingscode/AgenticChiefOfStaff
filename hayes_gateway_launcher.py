import asyncio
import sys
import runpy
import os

# 1. Fix the Windows 'Event loop is closed' error
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# 2. Add current directory to the path so it can see the 'nanobot' folder
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# ==========================================
# --- 3. SUBAGENT MCP MONKEY PATCH ---
# ==========================================
try:
    from nanobot.agent.loop import AgentLoop
    import nanobot.agent.subagent
    from nanobot.agent.tools.registry import ToolRegistry
    from nanobot.agent.subagent import SubagentManager

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

    # C. Inject the instruction into the subagent's system prompt
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

    print("[Launcher] Subagent MCP proxy patch applied successfully.")
except ImportError as e:
    print(f"[Launcher] Warning: Could not apply Subagent patch. {e}")
except Exception as e:
    print(f"[Launcher] Error applying Subagent patch: {e}")
# ==========================================

if __name__ == "__main__":
    # 4. Mimic the CLI arguments: 'nanobot gateway'
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