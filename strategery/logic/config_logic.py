from typing import Dict, Any, Optional, List
from pydantic import Field, ConfigDict, ValidationError
from nanobot.config.schema import Config, Base, AgentsConfig, AgentDefaults

# 1. Strategic Sub-models
class ContextPruningConfig(Base):
    enabled: bool = True
    ttl: str = "6h"
    keep_last_assistants: int = 3

class CompactionMemoryFlush(Base):
    enabled: bool = True
    prompt: str = "Store durable memories now."
    system_prompt: str = "Session nearing compaction."

class CompactionConfig(Base):
    enabled: bool = True
    memory_flush: CompactionMemoryFlush = Field(default_factory=CompactionMemoryFlush)

class MemoryRagConfig(Base):
    enabled: bool = True
    threshold: float = 0.7
    max_results: int = 5

class StrategicEditionConfig(Base):
    user_email: str = "admin@example.com"
    storage_root: str = "D:/Nanobot_Storage"
    app_root: str = "C:/Users/HayesChiefOfStaff/Documents/nanobot"
    storage_root_backup: Optional[str] = None
    backup_folder_id: Optional[str] = None
    memory_rag: MemoryRagConfig = Field(default_factory=MemoryRagConfig)
    disable_bot_commands: bool = False

# 2. Extension models that "bridge" the core models
class StrategicAgentDefaults(AgentDefaults):
    context_pruning: Optional[ContextPruningConfig] = Field(default=None)
    compaction: Optional[CompactionConfig] = Field(default=None)

class StrategicAgentsConfig(AgentsConfig):
    defaults: StrategicAgentDefaults = Field(default_factory=StrategicAgentDefaults)
    specialists: Dict[str, Any] = Field(default_factory=dict)
    heartbeat: Optional[Dict[str, Any]] = Field(default=None)
    consolidator: Optional[Dict[str, Any]] = Field(default=None)

# 3. Root Strategic Config
class StrategicConfig(Config):
    """
    Extensions to the core Nanobot Config schema for the Strategic Edition.
    Provides formal typing and validation for custom strategic keys.
    """
    # Override 'agents' with our strategic extension
    agents: StrategicAgentsConfig = Field(default_factory=StrategicAgentsConfig)
    
    # Add root strategic_edition key
    strategic_edition: StrategicEditionConfig = Field(default_factory=StrategicEditionConfig)

    # Allow extra fields for now to maintain core compatibility, 
    # but populate known strategic fields explicitly.
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

def validate_strategic_config(data: Dict[str, Any]) -> StrategicConfig:
    """
    Validates a raw dictionary against the StrategicConfig schema.
    Raises pydantic.ValidationError if critical fields are malformed.
    """
    # NOTE: We use model_validate to leverage Pydantic v2's performance and strictness.
    return StrategicConfig.model_validate(data)
