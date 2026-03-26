import builtins
from pathlib import Path

from strategery.logic import doctor_logic
from strategery.patches.config import load_strategic_context


def get_real_open():
    """Returns the original unpatched open function to bypass test mocks."""
    return getattr(builtins, "_orig_open_strategic", builtins.open)

def test_config_health(monkeypatch):
    """Verify that the main config.json is valid and lacks a BOM."""
    config_path = Path.home() / ".nanobot" / "config.json"

    # We must bypass the global_config_patch fixture to test the real file
    # We do this by monkeypatching 'open' back to the original for this test
    real_open = getattr(builtins, "orig_open", builtins.open) # From conftest
    if hasattr(builtins, "_orig_open_strategic"):
        real_open = builtins._orig_open_strategic

    with monkeypatch.context() as m:
        m.setattr(builtins, "open", real_open)
        ok, msg, config = doctor_logic.check_config_health(config_path)

        assert ok, f"Config Health Failure: {msg}"
        assert msg != "UTF-8 BOM detected", "Config contains a UTF-8 BOM (violates Mandate 3)."
        assert config is not None, "Config object could not be loaded."

def test_storage_pillars(monkeypatch):
    """Verify that the D: drive and critical memory files are accessible."""
    # Bypass mocks to see real storage
    real_open = getattr(builtins, "_orig_open_strategic", builtins.open)

    with monkeypatch.context() as m:
        m.setattr(builtins, "open", real_open)
        raw_cfg, user_email, storage_root = load_strategic_context()
        from strategery.logic.config_logic import validate_strategic_config
        config = validate_strategic_config(raw_cfg)

        checks = doctor_logic.check_storage_health(config)

        for name, ok, msg in checks:
            # We allow some files to be missing (WARN level in doctor),
            # but critical pillars must be present.
            if name in ["Root", "WriteAccess", "chroma.sqlite3", "checkpoints.db"]:
                assert ok, f"Critical Storage Pillar Missing: {name} ({msg})"

def test_mcp_executables(monkeypatch):
    """Verify that all configured MCP server commands are present on the system."""
    real_open = getattr(builtins, "_orig_open_strategic", builtins.open)
    with monkeypatch.context() as m:
        m.setattr(builtins, "open", real_open)
        raw_cfg, _, _ = load_strategic_context()
        from strategery.logic.config_logic import validate_strategic_config
        config = validate_strategic_config(raw_cfg)

        checks = doctor_logic.check_mcp_health(config)
        for name, ok, msg in checks:
            assert ok, f"MCP Executable Missing: {name} ({msg})"

def test_strategic_linter():
    """Perform static analysis on all strategic patches and logic files."""
    checks = doctor_logic.check_linter_health()
    for name, ok, msg in checks:
        assert ok, f"Static Analysis Failure in {name}: {msg}"

def test_patch_integrity(monkeypatch):
    """Verify that all strategic patches are correctly applied and active."""
    from strategery.patches import registry
    real_open = getattr(builtins, "_orig_open_strategic", builtins.open)
    with monkeypatch.context() as m:
        m.setattr(builtins, "open", real_open)
        raw_cfg, user_email, storage_root = load_strategic_context()
        from strategery.logic.config_logic import validate_strategic_config
        config = validate_strategic_config(raw_cfg)

        # Ensure patches are applied (in case this test runs in isolation)
        registry.apply_all(raw_cfg, storage_root=storage_root, user_email=user_email)

        for patch in registry._patches:
            assert patch.verify(config), f"Patch Integrity Failure: {patch.name} is not active or verified."
