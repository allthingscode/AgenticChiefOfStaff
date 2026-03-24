"""
DOCTOR LOGIC: Core recovery and repair functions for the Strategic Doctor.
Mandate: Decouple 'brains' from the CLI tool for 100% testability.
"""
import json
import os
from pathlib import Path
from typing import Optional, Dict, Any

def fix_config_bom(config_path: Path) -> bool:
    """Removes UTF-8 BOM and enforces 4-space indentation for config.json."""
    try:
        if not config_path.exists():
            return False
            
        # Read with utf-8-sig to handle existing BOM
        with open(config_path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
            
        # Write back with standard utf-8 (no BOM) and 4-space indent
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        return True
    except Exception:
        return False

def ensure_storage_structure(storage_root: Path) -> Dict[str, bool]:
    """Provisions missing strategic folder structures on the D: drive."""
    results = {}
    subdirs = [
        "logs",
        "workspace/memory/chroma",
        "workspace/cron/items",
        "workspace/media",
        "workspace/skills"
    ]
    
    for sd in subdirs:
        target = storage_root / sd
        if not target.exists():
            try:
                target.mkdir(parents=True, exist_ok=True)
                results[sd] = True
            except Exception:
                results[sd] = False
        else:
            results[sd] = False # Already exists
            
    return results

def initialize_strategic_manifest(manifest_path: Path) -> bool:
    """Creates a default BACKUP_MANIFEST.md if missing."""
    if manifest_path.exists():
        return False
        
    content = """# 🛡️ Strategic Backup Manifest
This file tracks the integrity and backup status of the Nanobot Strategic Edition storage root.

## **Storage Layout**
- `/logs`: Rolling session and diagnostic logs.
- `/workspace/memory`: ChromaDB and SQLite persistent memory.
- `/workspace/cron`: Modular batch job definitions.
- `/workspace/media`: Captured multimodal assets (images/docs).

## **Backup Status**
- [ ] Daily Knowledge Consolidation
- [ ] SQLite Checkpoint Integrity
- [ ] ChromaDB Snapshot

---
*Initialized by Strategic Doctor Auto-Heal.*
"""
    try:
        manifest_path.write_text(content.strip(), encoding="utf-8")
        return True
    except Exception:
        return False

def initialize_checkpoint_db(db_path: Path) -> bool:
    """Initializes the SQLite checkpoints database if missing."""
    if db_path.exists():
        return False
        
    try:
        # We import the logic here to avoid circular dependencies
        from strategery.logic.checkpoint_logic import CheckpointStore
        store = CheckpointStore(db_path=str(db_path))
        # Initializing the store automatically creates the tables
        return True
    except Exception:
        return False
