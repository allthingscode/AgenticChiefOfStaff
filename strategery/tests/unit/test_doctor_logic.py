import json
import builtins
from strategery.logic.doctor_logic import (
    fix_config_bom,
    ensure_storage_structure,
    initialize_strategic_manifest
)

def test_fix_config_bom(tmp_path):
    # Use .json_test to bypass the global 'open' patch in config.py
    # which forces utf-8-sig on .json files
    config_file = tmp_path / "config.json_test"
    
    # Create config with BOM and bad indent
    content = '\ufeff{\n"key": "value"\n}'
    config_file.write_text(content, encoding="utf-8")
    
    # Check if we have the original open available (from patches)
    # If not, use standard open but on a non-json extension
    open_func = getattr(builtins, "_orig_open_strategic", builtins.open)
    
    with open_func(config_file, "rb") as f:
        raw_before = f.read()
        # Direct byte comparison
        assert raw_before[:3] == b'\xef\xbb\xbf'

    assert fix_config_bom(config_file) is True
    
    # Verify BOM is gone
    with open_func(config_file, "rb") as f:
        raw_after = f.read()
        assert raw_after[:3] != b'\xef\xbb\xbf'
        
    # Verify content is valid JSON and indent is fixed
    with open_func(config_file, "r", encoding="utf-8") as f:
        data_loaded = json.load(f)
        assert data_loaded["key"] == "value"
        
    # Check 4-space indent
    text = config_file.read_text(encoding="utf-8")
    assert "    \"key\"" in text

def test_ensure_storage_structure(tmp_path):
    storage_root = tmp_path / "storage"
    storage_root.mkdir()
    
    results = ensure_storage_structure(storage_root)
    
    assert results["logs"] is True
    assert (storage_root / "logs").exists()
    assert (storage_root / "workspace/memory/chroma").exists()
    
    # Run again, should return False (already exists)
    results_again = ensure_storage_structure(storage_root)
    assert results_again["logs"] is False

def test_initialize_strategic_manifest(tmp_path):
    manifest_file = tmp_path / "BACKUP_MANIFEST.md"
    
    assert initialize_strategic_manifest(manifest_file) is True
    assert manifest_file.exists()
    assert "# 🛡️ Strategic Backup Manifest" in manifest_file.read_text(encoding="utf-8")
    
    # Run again, should not overwrite
    assert initialize_strategic_manifest(manifest_file) is False
