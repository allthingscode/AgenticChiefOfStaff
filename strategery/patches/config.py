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
        obj.pop("strategic_edition", None)
        obj.pop("memory", None)
        obj.pop("keywords", None)
        obj.pop("compaction", None)
        obj.pop("contextPruning", None)
        obj.pop("memorySearch", None)
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
            from nanobot.config.schema import Config
            
            # 1. Force the Config schema to ignore extra fields at runtime
            Config.model_config["extra"] = "ignore"
            
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
