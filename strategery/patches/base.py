from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

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

class BasePatch(ABC):
    """Base class for all strategic patches."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """The human-readable name of the patch."""
        pass

    @abstractmethod
    def apply(self, config_data: dict) -> PatchResult | bool:
        """
        Applies the patch using the provided configuration.
        Returns a PatchResult object (preferred) or True/False.
        """
        pass

    def verify(self, config_data: dict) -> bool:
        """
        Verifies that the patch was applied correctly and functions as expected.
        Default implementation returns True.
        """
        return True
