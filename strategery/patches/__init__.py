"""
Strategic Patch Registry: Modular infrastructure for Nanobot Strategic Edition.
This module provides the base classes and registry for applying runtime patches
without modifying the core Nanobot codebase.
"""

import sys
import os
from pathlib import Path
from typing import List, Dict, Any
from abc import ABC, abstractmethod

# Add project root to the path immediately
# This ensures that patches can import nanobot modules safely
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

class BasePatch(ABC):
    """Base class for all strategic patches."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """The display name of the patch."""
        pass

    @abstractmethod
    def apply(self, config_data: Dict[str, Any]) -> bool:
        """
        Apply the patch to the runtime environment.
        Args:
            config_data: The raw global configuration (RAW_CONFIG).
        Returns:
            True if applied successfully, False otherwise.
        """
        pass

class PatchRegistry:
    """Registry to manage and apply multiple strategic patches."""
    
    def __init__(self):
        self.patches: List[BasePatch] = []
        self._applied = False

    def register(self, patch: BasePatch):
        """Register a new patch."""
        self.patches.append(patch)

    def apply_all(self, config_data: Dict[str, Any]):
        """Apply all registered patches in order."""
        if self._applied:
            return
        
        for patch in self.patches:
            try:
                success = patch.apply(config_data)
                if success:
                    print(f"[Launcher] Patch applied: {patch.name}")
                else:
                    print(f"[Launcher] Warning: Patch failed to apply: {patch.name}")
            except Exception as e:
                print(f"[Launcher] Fatal error applying patch '{patch.name}': {e}")
        
        self._applied = True

# Global registry instance
registry = PatchRegistry()

# Import patches to register them
from .infra import InfraPatch
from .config import ConfigPatch, load_strategic_context
from .provider import ProviderPatch
from .memory import MemoryPatch
from .subagent import SubagentPatch
from .telegram import TelegramPatch

registry.register(InfraPatch())
registry.register(ConfigPatch())
registry.register(ProviderPatch())
registry.register(MemoryPatch())
registry.register(SubagentPatch())
registry.register(TelegramPatch())

# AUTOMATIC INITIALIZATION: 
# When this module is imported, we immediately apply the patches.
# This ensures that even when imported by tests (like test_agent_direct.py),
# the core patches are active.
RAW_CONFIG, USER_EMAIL, STORAGE_ROOT = load_strategic_context()
registry.apply_all(RAW_CONFIG)
