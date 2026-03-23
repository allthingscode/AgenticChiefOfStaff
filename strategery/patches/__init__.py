"""
Strategic Patch Registry: Modular infrastructure for Nanobot Strategic Edition.
This module provides the base classes and registry for applying runtime patches
without modifying the core Nanobot codebase.
"""

import sys
from pathlib import Path
from typing import List
from .base import BasePatch, PatchResult, PatchContext
from .infra import InfraPatch
from .config import ConfigPatch, load_strategic_context
from .provider import ProviderPatch
from .memory import MemoryPatch
from .subagent import SubagentPatch
from .telegram import TelegramPatch
from .cron import CronPatch
from .loop import AgentLoopPatch
from .session import SessionPatch
from .awareness import AwarenessPatch
from .email import EmailPatch
from strategery.strategic_logger import strategic_logger, setup_strategic_logger
from strategery.logic.config_logic import validate_strategic_config

class PatchRegistry:
    """Registry for managing and applying strategic patches."""
    
    def __init__(self):
        self._patches = [
            InfraPatch(),
            AgentLoopPatch(),
            SessionPatch(),
            ConfigPatch(),
            ProviderPatch(),
            MemoryPatch(),
            SubagentPatch(),
            TelegramPatch(),
            CronPatch(),
            AwarenessPatch(),
            EmailPatch()
        ]

    def apply_all(self, config_data: dict, halt_on_error: bool = False, **kwargs) -> List[PatchResult]:
        """Applies all registered patches in sequence."""
        # Check if already initialized in this process
        if getattr(sys, "_STRATEGIC_INITIALIZED", False):
            return []
            
        # 1. Resolve Global Context
        storage_root = kwargs.get("storage_root")
        user_email = kwargs.get("user_email", "admin@example.com")
        
        # Fallback resolution if not provided by launcher
        if not storage_root:
            _, _email, _root = load_strategic_context()
            storage_root = _root
            user_email = _email
            
        app_root = Path(__file__).parent.parent.parent
        
        # 2. Validate Config Schema (F-016)
        try:
            strategic_config = validate_strategic_config(config_data)
        except Exception as e:
            strategic_logger.critical(f"CONFIG VALIDATION FAILED: {e}")
            if halt_on_error:
                return [PatchResult(patch_name="Registry", success=False, error_msg=f"Config Validation Failed: {e}")]
            # Fallback to loose config if not halting, but this is dangerous
            strategic_config = config_data 

        # 3. Initialize Patch Context (F-018)
        context = PatchContext(
            config=strategic_config,
            storage_root=storage_root,
            user_email=user_email,
            app_root=app_root
        )
            
        # Ensure logger is correctly configured for the current environment/storage root
        setup_strategic_logger(log_dir=storage_root / "logs" if storage_root else None)
        strategic_logger.info("Applying Nanobot Strategic Edition patches...")
        
        results = []
        for patch in self._patches:
            try:
                # 1. Pre-Check Symbols (F-025 Guard)
                symbol_error = patch.check_symbols()
                if symbol_error:
                    error_res = PatchResult(
                        patch_name=patch.name,
                        success=False,
                        error_msg=f"Upstream Incompatibility: {symbol_error}"
                    )
                    results.append(error_res)
                    strategic_logger.error(f"Patch Guard: Skipping '{patch.name}' - {symbol_error}")
                    if halt_on_error:
                        break
                    continue

                # 2. Apply Patch with formal Context (F-018)
                res = patch.apply(context)
                
                # Handle legacy boolean returns for backward compatibility
                if isinstance(res, bool):
                    res = PatchResult(patch_name=patch.name, success=res)
                
                results.append(res)
                
                if res.success:
                    strategic_logger.debug(f"Patch applied: {patch.name}")
                else:
                    error_info = f" - {res.error_msg}" if res.error_msg else ""
                    strategic_logger.warning(f"Patch failed to apply: {patch.name}{error_info}")
                    if halt_on_error:
                        strategic_logger.error(f"HALTING: Critical failure in mandatory patch '{patch.name}'")
                        break
            except Exception as e:
                import traceback
                error_res = PatchResult(
                    patch_name=patch.name,
                    success=False,
                    error_msg=str(e),
                    traceback=traceback.format_exc()
                )
                results.append(error_res)
                strategic_logger.error(f"Patch execution crash: {patch.name} - {e}")
                if halt_on_error:
                    break
        
        # Set global flag on sys module to survive reloads within the same process
        setattr(sys, "_STRATEGIC_INITIALIZED", True)
        strategic_logger.info("Strategic Edition initialization complete.")
        return results

# Initialize global registry
registry = PatchRegistry()

# MANDATE: Auto-application removed in F-019. 
# Strategic components MUST explicitly call registry.apply_all() to modify the environment.
