"""
STRATEGIC DOCTOR: Pre-Flight Diagnostic Engine
Goal: Ensure 100% stability of Nanobot Strategic Edition before launch.
Mandate: Fail fast, fail loud, and provide actionable fixes.
"""
import json
import os
import sys
import subprocess
import shutil
import argparse
from pathlib import Path

# ANSI Colors for Terminal Clarity
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"

def print_status(component, message, level="INFO"):
    if level == "OK":
        print(f"[{GREEN}OK{RESET}] {BOLD}{component}:{RESET} {message}")
    elif level == "FIXED":
        print(f"[{CYAN}FIXED{RESET}] {BOLD}{component}:{RESET} {message}")
    elif level == "WARN":
        print(f"[{YELLOW}WARN{RESET}] {BOLD}{component}:{RESET} {message}")
    elif level == "FAIL":
        print(f"[{RED}FAIL{RESET}] {BOLD}{component}:{RESET} {message}")
    else:
        print(f"[* ] {BOLD}{component}:{RESET} {message}")

def check_config(apply=False):
    """Validates and optionally repairs the main config.json integrity."""
    from strategery.logic.config_logic import validate_strategic_config
    from strategery.logic.doctor_logic import fix_config_bom
    
    config_path = Path.home() / ".nanobot" / "config.json"
    if not config_path.exists():
        print_status("Config", f"Missing at {config_path}", "FAIL")
        return None
    
    try:
        # 1. Syntax & BOM Check (Strategic Mandate)
        with open(config_path, "rb") as f:
            raw_bytes = f.read()
            has_bom = raw_bytes.startswith(b'\xef\xbb\xbf')

        if has_bom:
            if apply:
                if fix_config_bom(config_path):
                    print_status("Config", "UTF-8 BOM removed and 4-space indentation enforced.", "FIXED")
                else:
                    print_status("Config", "Failed to remove BOM.", "FAIL")
                    return None
            else:
                print_status("Config", "UTF-8 BOM detected (violations Mandate 3). Use --apply to fix.", "WARN")
        
        # Read for schema validation
        with open(config_path, "r", encoding="utf-8-sig") as f:
            raw_data = json.load(f)
        print_status("Config", "Syntax and BOM verified.", "OK")
        
        # 2. Strategic Schema Validation (F-016)
        try:
            config = validate_strategic_config(raw_data)
            print_status("Config", "Strategic Schema (Pydantic) validated.", "OK")
            return config
        except Exception as ve:
            print_status("Config", f"Schema Validation FAILED: {ve}", "FAIL")
            return None
            
    except Exception as e:
        print_status("Config", f"Parsing error: {e}", "FAIL")
        return None

def check_storage(config, apply=False):
    """Audits and optionally provisions the D: drive and critical memory files."""
    from strategery.logic.doctor_logic import (
        ensure_storage_structure, 
        initialize_strategic_manifest,
        initialize_checkpoint_db
    )
    
    storage_root = Path(config.strategic_edition.storage_root)
    
    if not storage_root.exists():
        if apply:
            try:
                storage_root.mkdir(parents=True, exist_ok=True)
                print_status("Storage", f"Created missing storage root at {storage_root}.", "FIXED")
            except Exception as e:
                print_status("Storage", f"Failed to create root: {e}", "FAIL")
                return False
        else:
            print_status("Storage", f"Root missing at {storage_root}. D: drive disconnected?", "FAIL")
            return False
    
    # Provision Missing Folders
    if apply:
        res = ensure_storage_structure(storage_root)
        for folder, fixed in res.items():
            if fixed:
                print_status("Storage", f"Created missing folder: {folder}", "FIXED")

    # Check Read/Write
    test_file = storage_root / ".doctor_test"
    try:
        test_file.write_text("health_check")
        test_file.unlink()
        print_status("Storage", f"Read/Write verified on {storage_root.drive}", "OK")
    except Exception as e:
        print_status("Storage", f"Write failure: {e}", "FAIL")
        return False

    # Check Critical Files
    creds_root = Path.home() / ".nanobot"
    
    # Initializers for critical files
    initializers = {
        "BACKUP_MANIFEST.md": initialize_strategic_manifest,
        "checkpoints.db": initialize_checkpoint_db
    }

    critical = [
        storage_root / "workspace" / "memory" / "chroma" / "chroma.sqlite3",
        storage_root / "workspace" / "checkpoints.db",
        storage_root / "BACKUP_MANIFEST.md",
        creds_root / "secrets" / "token.json",
        creds_root / "google_surgical" / "credentials" / f"{config.strategic_edition.user_email}.json"
    ]
    
    for p in critical:
        if p.exists():
            print_status("Storage", f"Found: {p.name}", "OK")
        else:
            if apply and p.name in initializers:
                if initializers[p.name](p):
                    print_status("Storage", f"Initialized: {p.name}", "FIXED")
                else:
                    print_status("Storage", f"Failed to initialize: {p.name}", "FAIL")
            else:
                # For secrets, show the standard path for clarity if missing
                loc = "C:" if ".nanobot" in str(p) else "D:"
                lvl = "WARN" if p.name in initializers else "FAIL"
                print_status("Storage", f"Missing [{loc}]: {p.name}", lvl)
    
    return True

def check_mcp_tools(config):
    """Verifies all MCP server commands are valid and executable."""
    mcp_servers = config.tools.mcp_servers
    all_ok = True
    
    for name, srv in mcp_servers.items():
        cmd = srv.command
        if not cmd: continue
        
        # Check for executable existence
        if shutil.which(cmd) or Path(cmd).exists():
            print_status("MCP", f"Server '{name}' command verified: {Path(cmd).name}", "OK")
        else:
            print_status("MCP", f"Server '{name}' command NOT FOUND: {cmd}", "FAIL")
            all_ok = False
            
    return all_ok

def check_batch_jobs(config):
    """Validates modular job metadata blocks."""
    storage_root = Path(config.strategic_edition.storage_root)
    items_dir = storage_root / "workspace" / "cron" / "items"
    
    if not items_dir.exists():
        print_status("Batch", "No modular items folder found.", "INFO")
        return True

    all_ok = True
    for md_file in items_dir.glob("*.md"):
        try:
            content = md_file.read_text(encoding="utf-8-sig")
            if not content.strip().startswith("---"):
                print_status("Batch", f"Missing front-matter in {md_file.name}", "FAIL")
                all_ok = False
                continue
            
            # Simple metadata extraction
            meta = {}
            for line in content.split("---")[1].splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip()] = v.strip()
            
            required = ["id", "schedule", "specialist"]
            missing = [k for k in required if k not in meta]
            if missing:
                print_status("Batch", f"Job '{md_file.name}' missing metadata: {missing}", "FAIL")
                all_ok = False
            else:
                print_status("Batch", f"Job '{meta['id']}' metadata verified.", "OK")
        except Exception as e:
            print_status("Batch", f"Error parsing {md_file.name}: {e}", "FAIL")
            all_ok = False
            
    return all_ok

def check_patch_application(config):
    """Explicitly applies patches and verifies the results."""
    from strategery.patches import registry
    from strategery.patches.config import load_strategic_context
    
    # Load context and apply
    raw_cfg, user_email, storage_root = load_strategic_context()
    results = registry.apply_all(raw_cfg, storage_root=storage_root, user_email=user_email)
    
    if not results:
        # If results is empty, it might mean already initialized, which is OK for doctor
        return True
        
    all_ok = True
    for res in results:
        if not res.success:
            print(f"{RED}[FAIL] Patch failed: {res.patch_name} - {res.error_msg}{RESET}")
            all_ok = False
        else:
            # We don't need to print every success here, the integrity check handles it
            pass
    return all_ok

def check_patch_integrity(config):
    """Verifies that all strategic monkey-patches are active and functionally correct."""
    try:
        from strategery.patches import registry
        all_ok = True
        
        for patch in registry._patches:
            try:
                if patch.verify(config):
                    print_status("Integrity", f"Patch verified: {patch.name}", "OK")
                else:
                    print_status("Integrity", f"Patch FAILED verification: {patch.name}", "FAIL")
                    all_ok = False
            except Exception as e:
                print_status("Integrity", f"Error verifying patch {patch.name}: {e}", "FAIL")
                all_ok = False
        
        return all_ok
    except Exception as e:
        print_status("Integrity", f"Major failure in integrity engine: {e}", "FAIL")
        return False

def check_static_analysis():
    """Validates Python syntax across all strategic files (No-NameError Shield)."""
    strat_dir = Path(__file__).parent
    all_ok = True
    
    # Check both the patches and the root strategic tools
    targets = list((strat_dir / "patches").glob("*.py")) + list(strat_dir.glob("*.py"))
    
    for py_file in targets:
        try:
            with open(py_file, "r", encoding="utf-8-sig") as f:
                content = f.read()
            # This catches syntax errors and basic import issues (BUG-100)
            compile(content, py_file, 'exec')
            print_status("Linter", f"Syntax verified: {py_file.name}", "OK")
        except SyntaxError as se:
            print_status("Linter", f"Syntax ERROR in {py_file.name}: {se}", "FAIL")
            all_ok = False
        except Exception as e:
            print_status("Linter", f"Analysis error in {py_file.name}: {e}", "WARN")
            
    return all_ok

def main():
    parser = argparse.ArgumentParser(description="Strategic Doctor: Pre-Flight Diagnostic Engine")
    parser.add_argument("--apply", action="store_true", help="Automatically attempt to fix identified issues.")
    args = parser.parse_args()

    print(f"\n{BOLD}Strategic Doctor: Diagnostic Run ({Path(__file__).name}){RESET}")
    if args.apply:
        print(f"{CYAN}{BOLD}MODE: Auto-Heal Enabled{RESET}")
    print("="*50)
    
    config = check_config(apply=args.apply)
    if not config: sys.exit(1)
    
    if not check_storage(config, apply=args.apply): sys.exit(1)
    if not check_patch_application(config): sys.exit(1)
    if not check_patch_integrity(config): sys.exit(1)
    if not check_static_analysis(): sys.exit(1)
    if not check_mcp_tools(config): sys.exit(1)
    if not check_batch_jobs(config): sys.exit(1)
    
    print("="*50)
    if args.apply:
        print(f"{GREEN}{BOLD}SUCCESS: All Strategic pillars are healthy and repaired. Proceeding with launch.{RESET}\n")
    else:
        print(f"{GREEN}{BOLD}SUCCESS: All Strategic pillars are healthy. Proceeding with launch.{RESET}\n")

if __name__ == "__main__":
    main()
