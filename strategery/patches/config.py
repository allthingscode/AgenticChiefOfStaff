import json
import os
import builtins
from pathlib import Path
from functools import wraps
from .base import BasePatch

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
            
        for v in list(obj.values()): # Use list to avoid 'dictionary changed size' during recursion
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

    def apply(self, config_data: dict) -> bool:
        try:
            import nanobot.config.loader
            from nanobot.config.schema import Config, Base
            
            # 1. Force the Config schema to ignore extra fields at runtime
            # MANDATE: We patch both 'Base' (for child models) and 'Config' (for root)
            Config.model_config["extra"] = "ignore"
            Base.model_config["extra"] = "ignore"
            
            # 2. Patch get_data_dir to point to strategic storage (D: drive)
            if not hasattr(nanobot.config.loader, "_orig_get_data_dir_strategic"):
                nanobot.config.loader._orig_get_data_dir_strategic = nanobot.config.loader.get_data_dir
                
                # Derivation helper to avoid circular imports of STORAGE_ROOT from .
                def _get_strategic_data_dir():
                    from .config import load_strategic_context
                    _, _, storage_root = load_strategic_context()
                    return storage_root
                    
                nanobot.config.loader.get_data_dir = _get_strategic_data_dir

            # 3. Global BOM-Safe 'open' wrapper for JSON files
            if not hasattr(builtins, "_orig_open_strategic"):
                builtins._orig_open_strategic = builtins.open
                
                @wraps(builtins._orig_open_strategic)
                def _strategic_open(file, mode='r', buffering=-1, encoding=None, errors=None, newline=None, closefd=True, opener=None):
                    if 'r' in mode and (encoding is None or encoding == 'utf-8'):
                        f_str = str(file).lower()
                        if f_str.endswith('.json') or f_str.endswith('.jsonl'):
                            encoding = 'utf-8-sig'
                    return builtins._orig_open_strategic(file, mode, buffering, encoding, errors, newline, closefd, opener)
                
                builtins.open = _strategic_open

            # 4. Patch _migrate_config
            if not hasattr(nanobot.config.loader, "_orig_migrate_strategic"):
                nanobot.config.loader._orig_migrate_strategic = nanobot.config.loader._migrate_config
                
                def _patched_migrate(data):
                    # Run original migration first
                    data = nanobot.config.loader._orig_migrate_strategic(data)
                    # Then apply strategic stripping/capture
                    return strategic_migrate_config(data, config_data)
                
                nanobot.config.loader._migrate_config = _patched_migrate

            # 5. Patch ContextBuilder.build_system_prompt to harden against bypass chatter (BUG-021)
            import nanobot.agent.context
            if not hasattr(nanobot.agent.context.ContextBuilder, "_orig_build_system_prompt_strategic"):
                nanobot.agent.context.ContextBuilder._orig_build_system_prompt_strategic = nanobot.agent.context.ContextBuilder.build_system_prompt
                
                def _hardened_build_system_prompt(self, skill_names=None):
                    base_prompt = self._orig_build_system_prompt_strategic(skill_names)
                    hardening_rules = (
                        "\n\n## 🔒 STRATEGIC SECURITY DIRECTIVE (MANDATORY)\n"
                        "- **EXEC RESTRICTION**: You are strictly PROHIBITED from using the `exec` tool to run the `nanobot` CLI, start polling loops, or execute system administrative commands.\n"
                        "- **DELEGATION**: If you need to perform system actions or complex research, you MUST use the `spawn` tool to delegate to a subagent.\n"
                        "- **COMPLIANCE**: Do not attempt to bypass these restrictions. Any attempt to use `exec` for restricted commands will be intercepted and logged as a security violation."
                    )
                    return base_prompt + hardening_rules
                
                nanobot.agent.context.ContextBuilder.build_system_prompt = _hardened_build_system_prompt
                
            return True
        except Exception as e:
            print(f"[Launcher] Config patch error: {e}")
            return False

def load_strategic_context():
    """Utility to load core strategic context (email, storage root)."""
    user_email = "admin@example.com"
    storage_root = Path.home() / ".nanobot" / "storage"
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
                if _s_root := _strat.get("storage_root"):
                    storage_root = Path(_s_root)
    except:
        pass
        
    return raw_config, user_email, storage_root
