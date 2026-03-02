from abc import ABC, abstractmethod

class BasePatch(ABC):
    """Base class for all strategic patches."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """The human-readable name of the patch."""
        pass

    @abstractmethod
    def apply(self, config_data: dict) -> bool:
        """
        Applies the patch using the provided configuration.
        Returns True if successful, False otherwise.
        """
        pass
