"""BUG-257: Verify that a config validation failure falls back to StrategicConfig,
not a raw dict, so patches that access context.config.strategic_edition don't crash."""
import sys
from unittest.mock import patch

import pytest

from strategery.logic.config_logic import StrategicConfig
from strategery.patches import PatchRegistry


@pytest.fixture(autouse=True)
def reset_strategic_initialized():
    """Reset the process-level init guard so each test runs apply_all fresh."""
    sys._STRATEGIC_INITIALIZED = False
    yield
    sys._STRATEGIC_INITIALIZED = False


def test_config_validation_fallback_is_strategic_config():
    """When validate_strategic_config raises, context.config must be a StrategicConfig,
    not a raw dict — otherwise typed patches (Telegram, Memory) crash with AttributeError."""
    captured = {}

    class CapturingPatch:
        name = "capturing"
        def check_symbols(self): return None
        def apply(self, context):
            captured["config"] = context.config
            from strategery.patches.base import PatchResult
            return PatchResult(patch_name=self.name, success=True)

    registry = PatchRegistry()
    registry._patches = [CapturingPatch()]

    with patch("strategery.patches.validate_strategic_config", side_effect=ValueError("bad config")):
        registry.apply_all({"bad": "data"}, halt_on_error=False)

    assert "config" in captured, "Patch was never called"
    assert isinstance(captured["config"], StrategicConfig), (
        f"Expected StrategicConfig fallback, got {type(captured['config']).__name__} — "
        "this would crash any patch accessing .strategic_edition"
    )


def test_config_validation_fallback_attribute_access():
    """Verify .strategic_edition and .agents are accessible on the fallback config."""
    captured = {}

    class CapturingPatch:
        name = "capturing"
        def check_symbols(self): return None
        def apply(self, context):
            captured["config"] = context.config
            from strategery.patches.base import PatchResult
            return PatchResult(patch_name=self.name, success=True)

    registry = PatchRegistry()
    registry._patches = [CapturingPatch()]

    with patch("strategery.patches.validate_strategic_config", side_effect=ValueError("bad config")):
        registry.apply_all({}, halt_on_error=False)

    config = captured["config"]
    # These attribute accesses must not raise — they're what Telegram and Memory patches use
    _ = config.strategic_edition.disable_bot_commands
    _ = config.strategic_edition.memory_rag
    _ = config.agents
