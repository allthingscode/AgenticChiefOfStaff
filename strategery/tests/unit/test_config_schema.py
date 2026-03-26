import pytest
from pydantic import ValidationError

from strategery.logic.config_logic import StrategicConfig, validate_strategic_config


def test_valid_strategic_config():
    """Verify that a complete strategic configuration validates correctly."""
    raw_data = {
        "agents": {
            "defaults": {
                "model": "gpt-4",
                "contextPruning": {
                    "enabled": True,
                    "ttl": "12h",
                    "keepLastAssistants": 5
                },
                "compaction": {
                    "enabled": True,
                    "memoryFlush": {
                        "enabled": True,
                        "prompt": "Test Prompt"
                    }
                }
            },
            "specialists": {
                "researcher": {"model": "researcher-model"},
                "architect": {"model": "architect-model"}
            },
            "heartbeat": {"model": "hb-model"}
        },
        "strategic_edition": {
            "user_email": "test@example.com",
            "storage_root": "D:/Test",
            "memory_rag": {"enabled": False}
        }
    }

    config = validate_strategic_config(raw_data)
    assert isinstance(config, StrategicConfig)
    assert config.strategic_edition.user_email == "test@example.com"
    assert config.agents.defaults.context_pruning.ttl == "12h"
    assert config.agents.specialists["researcher"]["model"] == "researcher-model"
    assert config.agents.heartbeat["model"] == "hb-model"

def test_invalid_strategic_config_types():
    """Verify that malformed types trigger a ValidationError."""
    raw_data = {
        "strategic_edition": {
            "user_email": "test@example.com",
            "storage_root": 12345 # Should be string
        }
    }
    with pytest.raises(ValidationError):
        validate_strategic_config(raw_data)

def test_config_defaults():
    """Verify that defaults are populated when keys are missing."""
    raw_data = {
        "strategic_edition": {
            "user_email": "test@example.com"
        }
    }
    config = validate_strategic_config(raw_data)
    # Check default storage_root from schema
    assert config.strategic_edition.storage_root == "D:/Nanobot_Storage"
    # Check nested defaults
    assert config.agents.defaults.context_pruning is None # Default in schema is None if not provided

def test_extra_fields_ignored():
    """Verify that unknown keys are ignored (extra='ignore')."""
    raw_data = {
        "strategic_edition": {
            "user_email": "test@example.com",
            "unknown_key": "ignore_me"
        },
        "unknown_root_key": "ignore_me_too"
    }
    config = validate_strategic_config(raw_data)
    assert config.strategic_edition.user_email == "test@example.com"
    # Pydantic with extra='ignore' will just drop these from the model
    assert not hasattr(config, "unknown_root_key")
