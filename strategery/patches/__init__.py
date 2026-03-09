"""
Strategic Patch Registry: Modular infrastructure for Nanobot Strategic Edition.
This module provides the base classes and registry for applying runtime patches
without modifying the core Nanobot codebase.
"""

import sys
from typing import List
from .base import BasePatch, PatchResult
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
from strategery.strategic_logger import strategic_logger, setup_strategic_logger

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
            AwarenessPatch()
        ]

    def apply_all(self, config_data: dict, halt_on_error: bool = False, **kwargs) -> List[PatchResult]:
        """Applies all registered patches in sequence."""
        # Check if already initialized in this process
        if getattr(sys, "_STRATEGIC_INITIALIZED", False):
            return []
            
        # Ensure logger is correctly configured for the current environment/storage root
        setup_strategic_logger()
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

                # 2. Apply Patch
                res = patch.apply(config_data)
                
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
