"""
STRATEGIC DOCTOR: Pre-Flight Diagnostic Engine
Goal: Ensure 100% stability of Nanobot Strategic Edition before launch.
Mandate: Fail fast, fail loud, and provide actionable fixes.
"""
import sys
import argparse
from pathlib import Path
from strategery.logic import doctor_logic

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
    config_path = Path.home() / ".nanobot" / "config.json"
    ok, msg, config = doctor_logic.check_config_health(config_path)
    
    if ok:
        if msg == "UTF-8 BOM detected":
            if apply:
                if doctor_logic.fix_config_bom(config_path):
                    print_status("Config", "UTF-8 BOM removed and 4-space indentation enforced.", "FIXED")
                    # Re-read after fix
                    _, _, config = doctor_logic.check_config_health(config_path)
                else:
                    print_status("Config", "Failed to remove BOM.", "FAIL")
                    return None
            else:
                print_status("Config", "UTF-8 BOM detected (violations Mandate 3). Use --apply to fix.", "WARN")
        else:
            print_status("Config", "Syntax and BOM verified.", "OK")
            print_status("Config", "Strategic Schema (Pydantic) validated.", "OK")
        return config
    else:
        print_status("Config", f"Failure: {msg}", "FAIL")
        return None

def check_storage(config, apply=False):
    """Audits and optionally provisions the D: drive and critical memory files."""
    storage_root = Path(config.strategic_edition.storage_root)

    # Root Provisioning
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
        res = doctor_logic.ensure_storage_structure(storage_root)
        for folder, fixed in res.items():
            if fixed:
                print_status("Storage", f"Created missing folder: {folder}", "FIXED")

    # Critical Initializers
    initializers = {
        "BACKUP_MANIFEST.md": doctor_logic.initialize_strategic_manifest,
        "checkpoints.db": doctor_logic.initialize_checkpoint_db
    }

    checks = doctor_logic.check_storage_health(config)
    all_ok = True
    for name, ok, msg in checks:
        if ok:
            print_status("Storage", f"{name}: {msg}", "OK")
        else:
            if apply and name in initializers:
                p = storage_root / name if "D:" in str(storage_root) else Path.home() / ".nanobot" / name
                if initializers[name](p):
                    print_status("Storage", f"Initialized: {name}", "FIXED")
                else:
                    print_status("Storage", f"Failed to initialize: {name}", "FAIL")
                    all_ok = False
            else:
                lvl = "WARN" if name in initializers else "FAIL"
                print_status("Storage", f"{name}: {msg}", lvl)
                if lvl == "FAIL": all_ok = False
    return all_ok

def check_mcp_tools(config):
    """Verifies all MCP server commands are valid and executable."""
    checks = doctor_logic.check_mcp_health(config)
    all_ok = True
    for name, ok, msg in checks:
        if ok:
            print_status("MCP", f"Server '{name}' command verified: {msg.split(': ')[1]}", "OK")
        else:
            print_status("MCP", f"Server '{name}' command {msg}", "FAIL")
            all_ok = False
    return all_ok

def check_batch_jobs(config):
    """Validates modular job metadata blocks."""
    checks = doctor_logic.check_batch_health(config)
    all_ok = True
    for name, ok, msg in checks:
        if ok:
            print_status("Batch", f"Job '{name}' metadata verified.", "OK")
        else:
            print_status("Batch", f"Job '{name}' error: {msg}", "FAIL")
            all_ok = False
    return all_ok

def check_patch_application(config):
    """Explicitly applies patches and verifies the results."""
    from strategery.patches import registry
    from strategery.patches.config import load_strategic_context

    raw_cfg, user_email, storage_root = load_strategic_context()
    results = registry.apply_all(raw_cfg, storage_root=storage_root, user_email=user_email)

    if not results: return True

    all_ok = True
    for res in results:
        if not res.success:
            print(f"{RED}[FAIL] Patch failed: {res.patch_name} - {res.error_msg}{RESET}")
            all_ok = False
    return all_ok

def check_patch_integrity(config):
    """Verifies that all strategic monkey-patches are active and functionally correct."""
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

def check_static_analysis(apply=False):
    """Validates Python syntax across all strategic files."""
    checks = doctor_logic.check_linter_health(apply=apply)
    all_ok = True
    for name, ok, msg in checks:
        if ok:
            print_status("Linter", f"Syntax verified: {name}", "OK")
        else:
            print_status("Linter", f"Error in {name}: {msg}", "FAIL")
            all_ok = False
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
    print(f"{GREEN}{BOLD}SUCCESS: All Strategic pillars are healthy. Proceeding with launch.{RESET}\n")

if __name__ == "__main__":
    main()
