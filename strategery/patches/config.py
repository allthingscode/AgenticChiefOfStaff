import json
import os
import builtins
from pathlib import Path
from functools import wraps
from typing import TYPE_CHECKING
from .base import BasePatch, PatchResult, PatchContext

if TYPE_CHECKING:
    pass

def strategic_migrate_config(data, config_data_capture=None):
    """
    Strategic migration logic: 
    1. Captures raw config.
    2. Runs original migration (via caller).
    3. Strips custom keys for Pydantic.
    """
    if data and isinstance(data, dict) and config_data_capture is not None:
        config_data_capture.clear()
        config_data_capture.update(json.loads(json.dumps(data)))
    
    # Surgical strip of custom keys
    def _strip_recursively(obj):
        if not isinstance(obj, dict): return
        # Mandate: Remove all strategic-specific keys to prevent Pydantic validation errors
        # This list must be comprehensive based on everything injected in config.json
        keys_to_strip = [
            "strategic_edition", "memory", "keywords", "compaction", 
            "contextPruning", "memorySearch", "user_email", "storage_path", 
            "storage_root", "storage_root_backup", "app_root"
        ]
        for key in keys_to_strip:
            obj.pop(key, None)

        for k, v in list(obj.items()):
            if k in keys_to_strip:
                obj.pop(k, None)
                continue
            if isinstance(v, (dict, list)):
                if isinstance(v, list):
                    for item in v:
                        if isinstance(item, dict): _strip_recursively(item)
                else:
                    _strip_recursively(v)
    
    _strip_recursively(data)
    return data

class ConfigPatch(BasePatch):
    """Handles global configuration overrides, BOM handling, and RAW_CONFIG management."""

    @property
    def name(self) -> str:
        return "Configuration & Schema Overrides"

    def apply(self, context: PatchContext) -> PatchResult:
        result = PatchResult(patch_name=self.name, success=True)
        try:
            import nanobot.config.loader
            from nanobot.config.schema import Config, Base

            # 1. Force the Config schema to ignore extra fields at runtime
            if isinstance(Config.model_config, dict):
                Config.model_config["extra"] = "ignore"
            else:
                Config.model_config = {**Config.model_config, "extra": "ignore"}

            if isinstance(Base.model_config, dict):
                Base.model_config["extra"] = "ignore"
            else:
                Base.model_config = {**Base.model_config, "extra": "ignore"}
            result.affected_symbols.append("Config.model_config (extra=ignore)")

            # 2. Patch get_data_dir to point to strategic storage (D: drive)
            import nanobot.config.paths
            if not hasattr(nanobot.config.paths, "_orig_get_data_dir_strategic"):
                nanobot.config.paths._orig_get_data_dir_strategic = nanobot.config.paths.get_data_dir

                def _get_strategic_data_dir():
                    return context.storage_root

                nanobot.config.paths.get_data_dir = _get_strategic_data_dir
                result.affected_symbols.append("nanobot.config.paths.get_data_dir")

                if hasattr(nanobot.config.paths, "get_workspace_path"):
                    nanobot.config.paths._orig_get_workspace_path_strategic = nanobot.config.paths.get_workspace_path
                    def _get_strategic_workspace_path(workspace=None):
                        if workspace:
                            return Path(workspace).expanduser()
                        return context.workspace_root
                    
                    nanobot.config.paths.get_workspace_path = _get_strategic_workspace_path
                    result.affected_symbols.append("nanobot.config.paths.get_workspace_path")

                if hasattr(Config, "workspace_path"):
                    @property
                    def _strategic_workspace_path(self):
                        return context.workspace_root

                    Config.workspace_path = _strategic_workspace_path
                    result.affected_symbols.append("Config.workspace_path")

            # 3. Global BOM-Safe 'open' wrapper for JSON files
            if not hasattr(builtins, "_orig_open_strategic"):
                builtins._orig_open_strategic = builtins.open
                
                @wraps(builtins._orig_open_strategic)
                def _strategic_open(file, mode='r', buffering=-1, encoding=None, errors=None, newline=None, closefd=True, opener=None):
                    if 'r' in mode and 'b' not in mode and (encoding is None or encoding == 'utf-8'):
                        f_str = str(file).lower()
                        if f_str.endswith('.json') or f_str.endswith('.jsonl'):
                            encoding = 'utf-8-sig'
                    return builtins._orig_open_strategic(file, mode, buffering, encoding, errors, newline, closefd, opener)
                
                builtins.open = _strategic_open
                result.affected_symbols.append("builtins.open (BOM-safe)")

            # 4. Patch _migrate_config
            if not hasattr(nanobot.config.loader, "_orig_migrate_strategic"):
                nanobot.config.loader._orig_migrate_strategic = nanobot.config.loader._migrate_config
                
                def _patched_migrate(data):
                    data = nanobot.config.loader._orig_migrate_strategic(data)
                    # For legacy compatibility, we dump the StrategicConfig back to a dict for the stripper
                    if not isinstance(context.config, dict):
                        config_dict = context.config.model_dump(by_alias=True)
                    else:
                        config_dict = context.config
                    return strategic_migrate_config(data, config_dict)
                
                nanobot.config.loader._migrate_config = _patched_migrate
                result.affected_symbols.append("nanobot.config.loader._migrate_config")

            # 5. Patch ContextBuilder.build_system_prompt to harden against bypass chatter (BUG-021)
            import nanobot.agent.context
            if not hasattr(nanobot.agent.context.ContextBuilder, "_orig_build_system_prompt_strategic"):
                nanobot.agent.context.ContextBuilder._orig_build_system_prompt_strategic = nanobot.agent.context.ContextBuilder.build_system_prompt
                
                def _hardened_build_system_prompt(self, skill_names=None):
                    base_prompt = self._orig_build_system_prompt_strategic(skill_names)
                    storage_root = context.storage_root
                    hardening_rules = (
                        "\n\n## 🛡️ STRATEGIC MANDATE (MANDATORY)\n"
                        "- **EXEC RESTRICTION**: You are strictly PROHIBITED from using the `exec` tool to run the `nanobot` CLI, start polling loops, or execute system administrative commands.\n"
                        "- **DELEGATION**: High-power tools (Google AI Search, Email, Strategic CLI) are RESTRICTED. You MUST use the `spawn` tool to delegate these tasks to a specialist subagent.\n"
                        "- **ORCHESTRATION INTEGRITY**: When using the `spawn` tool, NEVER attempt to predict, hallucinate, or state a subagent ID (e.g., ID: 6729081b) in your initial turn. The true ID is only generated by the system AFTER your turn. Simply state your intent to spawn and end the turn immediately.\n"
                        f"- **STORAGE DOMAIN**: The storage root (`{storage_root}`) is the exclusive domain of specialists. You are strictly PROHIBITED from using `exec` (e.g. `ls`, `dir`) or `list_dir` to inspect storage. Spawn a specialist for all storage operations.\n"
                        "- **MEMORY MANAGEMENT**: DO NOT attempt to manually write to `history.md`, `memory.json`, or any log files using `exec` or `write_file`. The system's automated consolidation protocol manages all long-term memory. Any attempt to manually manage history will be intercepted.\n"
                        "- **DO NOT CALL DIRECTLY**: Any attempt to call specialist tools (e.g. `mcp_google-ai-search_search_ai`, `mcp_email-reporter_send_email_report`) from the Main Agent will be BLOCKED. You are an ORCHESTRATOR, not a researcher.\n"
                        "- **COMPLIANCE**: If you need to search, verify facts, or perform system operations, spawn a specialist subagent immediately and wait for the result via the message bus."
                    )
                    return base_prompt + hardening_rules
                
                nanobot.agent.context.ContextBuilder.build_system_prompt = _hardened_build_system_prompt
                result.affected_symbols.append("ContextBuilder.build_system_prompt")
                
            return result
        except Exception as e:
            import traceback
            result.success = False
            result.error_msg = str(e)
            result.traceback = traceback.format_exc()
            print(f"[Launcher] Config patch error: {e}")
            return result

    def verify(self, config_data: dict) -> bool:
        """Verifies that the global 'open', ContextBuilder, and Path patches are active."""
        import builtins
        import nanobot.agent.context
        import nanobot.config.paths
        
        # 1. Check builtins.open
        if not hasattr(builtins, "_orig_open_strategic"):
            return False
            
        # 2. Check ContextBuilder.build_system_prompt
        if not hasattr(nanobot.agent.context.ContextBuilder, "_orig_build_system_prompt_strategic"):
            return False
            
        # 3. Check nanobot.config.paths.get_data_dir
        if not hasattr(nanobot.config.paths, "_orig_get_data_dir_strategic"):
            return False
            
        return True

def load_strategic_context():
    """Utility to load core strategic context (email, storage root)."""
    user_email = "admin@example.com"
    
    # BUG-FIX: Remove hard-coded D: drive default. Use env var or portable default.
    # The 'D:/Nanobot_Storage' mandate should be configured in config.json, not code.
    storage_root = Path(os.environ.get("STRATEGIC_STORAGE_ROOT", Path.home() / ".nanobot" / "storage"))
    raw_config = {}

    try:
        home_config = Path.home() / ".nanobot" / "config.json"
        if home_config.exists():
            # Use original open to avoid recursion during bootstrap
            with builtins.open(home_config, "r", encoding="utf-8-sig") as f:
                _raw = json.load(f)
                raw_config = _raw
                _strat = _raw.get("strategic_edition", {})
                user_email = _strat.get("user_email", user_email)
                
                # Prioritize explicit top-level storage_root (if any) then strategic_edition
                _s_root = _raw.get("storage_root") or _strat.get("storage_root")
                if _s_root:
                    storage_root = Path(_s_root)
    except:
        pass
        
    return raw_config, user_email, storage_root
