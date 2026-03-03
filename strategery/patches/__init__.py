"""
Strategic Patch Registry: Modular infrastructure for Nanobot Strategic Edition.
This module provides the base classes and registry for applying runtime patches
without modifying the core Nanobot codebase.
"""

from .base import BasePatch
from .infra import InfraPatch
from .config import ConfigPatch, load_strategic_context
from .provider import ProviderPatch
from .memory import MemoryPatch
from .subagent import SubagentPatch
from .telegram import TelegramPatch
from .vector_store import StrategicVectorStore
from strategery.strategic_logger import strategic_logger, setup_strategic_logger

class PatchRegistry:
    """Registry for managing and applying strategic patches."""
    
    def __init__(self):
        self._patches = [
            InfraPatch(),
            ConfigPatch(),
            ProviderPatch(),
            MemoryPatch(),
            SubagentPatch(),
            TelegramPatch()
        ]

    def apply_all(self, config_data: dict, **kwargs) -> dict:
        """Applies all registered patches in sequence."""
        # Ensure logger is correctly configured for the current environment/storage root
        setup_strategic_logger()
        strategic_logger.info("Applying Nanobot Strategic Edition patches...")
        
        results = {}
        for patch in self._patches:
            try:
                success = patch.apply(config_data)
                results[patch.name] = "Applied" if success else "Failed"
                if success:
                    strategic_logger.debug(f"Patch applied: {patch.name}")
                else:
                    strategic_logger.warning(f"Patch failed to apply: {patch.name}")
            except Exception as e:
                results[patch.name] = f"Error: {e}"
                strategic_logger.error(f"{patch.name} patch error: {e}")
        
        strategic_logger.info("Strategic Edition initialization complete.")
        return results

# Initialize global registry
registry = PatchRegistry()

# Auto-apply patches on import to ensure environment is set up correctly
# This ensures that even when imported by tests (like test_agent_direct.py),
# the core patches are active.
RAW_CONFIG, USER_EMAIL, STORAGE_ROOT = load_strategic_context()

# Re-initialize logger with strategic storage root if available
if STORAGE_ROOT:
    setup_strategic_logger(log_dir=STORAGE_ROOT / "logs")

registry.apply_all(RAW_CONFIG, storage_root=STORAGE_ROOT, user_email=USER_EMAIL)
