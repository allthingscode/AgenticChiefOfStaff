from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from pathlib import Path
import importlib

@dataclass
class PatchResult:
    """Detailed outcome of a patch application."""
    patch_name: str
    success: bool
    error_msg: Optional[str] = None
    traceback: Optional[str] = None
    affected_symbols: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __bool__(self) -> bool:
        """Allow the result to be used in boolean contexts for backward compatibility."""
        return self.success

@dataclass
class PatchContext:
    """Encapsulates the environment and configuration for a strategic patch."""
    config: Dict[str, Any]
    storage_root: Path
    user_email: str
    app_root: Path
    
    @property
    def workspace_root(self) -> Path:
        return self.storage_root / "workspace"

class BasePatch(ABC):
    """Base class for all strategic patches."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """The human-readable name of the patch."""
        pass

    @property
    def required_symbols(self) -> List[str]:
        """
        List of dot-notated symbols that MUST exist for this patch to be safe.
        Example: ["nanobot.providers.litellm.LiteLLMProvider.chat"]
        """
        return []

    @abstractmethod
    def apply(self, context: PatchContext) -> PatchResult | bool:
        """
        Applies the patch using the provided context.
        Returns a PatchResult object (preferred) or True/False.
        """
        pass

    def verify(self, config_data: dict) -> bool:
        """
        Verifies that the patch was applied correctly and functions as expected.
        Default implementation returns True.
        """
        return True

    def check_symbols(self) -> Optional[str]:
        """
        Verifies that all required symbols exist in the core codebase.
        Returns None if all OK, or an error message identifying the missing symbol.
        """
        for sym in self.required_symbols:
            parts = sym.split('.')
            # Walk up the path to find the module and attribute
            # We assume at least 'module.attribute'
            if len(parts) < 2:
                continue
                
            module_name = ""
            target = None
            
            # Try to find the break point between module and attribute
            # We iterate backwards to find the longest valid module path
            found_module = False
            for i in range(len(parts) - 1, 0, -1):
                try:
                    module_name = ".".join(parts[:i])
                    target = importlib.import_module(module_name)
                    remaining = parts[i:]
                    found_module = True
                    break
                except ImportError:
                    continue
            
            if not found_module:
                return f"Module for symbol '{sym}' could not be imported."
            
            # Now walk the attributes
            current = target
            for attr in remaining:
                if not hasattr(current, attr):
                    return f"Symbol '{attr}' missing from '{module_name}' (Target: {sym})"
                current = getattr(current, attr)
                
        return None
