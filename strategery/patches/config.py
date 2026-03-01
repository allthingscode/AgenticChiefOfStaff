import json
import os
from pathlib import Path
from . import BasePatch

class ConfigPatch(BasePatch):
    """Handles global configuration overrides, BOM handling, and RAW_CONFIG management."""
    
    @property
    def name(self) -> str:
        return "Configuration & Schema Overrides"

    def apply(self, config_data: dict) -> bool:
        # Note: config_data here is a reference to the global RAW_CONFIG 
        # that we will populate if it's empty, or update if it's not.
        
        try:
            import nanobot.config.loader
            from nanobot.config.schema import Config
            
            # 1. Force the Config schema to ignore extra fields at runtime
            Config.model_config["extra"] = "ignore"
            
            # 2. Patch load_config to use utf-8-sig
            if not hasattr(nanobot.config.loader, "_orig_load_config_strategic"):
                nanobot.config.loader._orig_load_config_strategic = nanobot.config.loader.load_config
                
                def _strategic_load_config(config_path=None):
                    path = config_path or nanobot.config.loader.get_config_path()
                    if path.exists():
                        try:
                            with open(path, "r", encoding="utf-8-sig") as f:
                                data = json.load(f)
                            return Config.model_validate(nanobot.config.loader._migrate_config(data))
                        except Exception as e:
                            print(f"[Launcher] Warning: Failed to load config: {e}")
                    return Config()
                
                nanobot.config.loader.load_config = _strategic_load_config

            # 3. Patch _migrate_config to capture RAW_CONFIG
            if not hasattr(nanobot.config.loader, "_orig_migrate_strategic"):
                nanobot.config.loader._orig_migrate_strategic = nanobot.config.loader._migrate_config
                
                def _patched_migrate(data):
                    # Update the provided config_data (which should be RAW_CONFIG)
                    config_data.clear()
                    config_data.update(json.loads(json.dumps(data)))
                    
                    # Run the original migration
                    data = nanobot.config.loader._orig_migrate_strategic(data)
                    
                    # Strip custom keys for Pydantic
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
            with open(home_config, "r", encoding="utf-8-sig") as f:
                _raw = json.load(f)
                raw_config = _raw
                _strat = _raw.get("strategic_edition", {})
                user_email = _strat.get("user_email", user_email)
                if _s_root := _strat.get("storage_root"):
                    storage_root = Path(_s_root)
    except:
        pass
        
    return raw_config, user_email, storage_root
