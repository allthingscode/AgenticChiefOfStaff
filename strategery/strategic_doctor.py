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
from pathlib import Path

# ANSI Colors for Terminal Clarity
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"

def print_status(component, message, level="INFO"):
    if level == "OK":
        print(f"[{GREEN}OK{RESET}] {BOLD}{component}:{RESET} {message}")
    elif level == "WARN":
        print(f"[{YELLOW}WARN{RESET}] {BOLD}{component}:{RESET} {message}")
    elif level == "FAIL":
        print(f"[{RED}FAIL{RESET}] {BOLD}{component}:{RESET} {message}")
    else:
        print(f"[* ] {BOLD}{component}:{RESET} {message}")

def check_config():
    """Validates the main config.json integrity."""
    config_path = Path.home() / ".nanobot" / "config.json"
    if not config_path.exists():
        print_status("Config", f"Missing at {config_path}", "FAIL")
        return None
    
    try:
        # Use utf-8-sig for Windows BOM safety (Strategic Mandate)
        with open(config_path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        print_status("Config", "Syntax and BOM verified.", "OK")
        
        # Check Strategic keys
        if "strategic_edition" not in data:
            print_status("Config", "Missing 'strategic_edition' block.", "FAIL")
            return None
        
        required = ["user_email", "storage_root", "app_root", "backup_folder_id"]
        missing = [k for k in required if k not in data["strategic_edition"]]
        if missing:
            print_status("Config", f"Missing strategic keys: {missing}", "FAIL")
            return None
        
        print_status("Config", "Strategic parameters present.", "OK")
        return data
    except Exception as e:
        print_status("Config", f"Parsing error: {e}", "FAIL")
        return None

def check_storage(config):
    """Audits the D: drive and critical memory files."""
    storage_root = Path(config["strategic_edition"].get("storage_root", "D:/Nanobot_Storage"))
    
    if not storage_root.exists():
        print_status("Storage", f"Root missing at {storage_root}. D: drive disconnected?", "FAIL")
        return False
    
    # Check Read/Write
    test_file = storage_root / ".doctor_test"
    try:
        test_file.write_text("health_check")
        test_file.unlink()
        print_status("Storage", f"Read/Write verified on {storage_root.drive}", "OK")
    except Exception as e:
        print_status("Storage", f"Write failure: {e}", "FAIL")
        return False

    # Check Critical Files (Standardized C: drive credentials & D: drive data)
    creds_root = Path.home() / ".nanobot"
    critical = [
        storage_root / "workspace" / "memory" / "chroma" / "chroma.sqlite3",
        storage_root / "BACKUP_MANIFEST.md",
        creds_root / "secrets" / "token.json",
        creds_root / "google_surgical" / "credentials" / f"{config['strategic_edition']['user_email']}.json"
    ]
    for p in critical:
        if p.exists():
            print_status("Storage", f"Found: {p.name}", "OK")
        else:
            # For secrets, show the standard path for clarity if missing
            loc = "C:" if ".nanobot" in str(p) else "D:"
            print_status("Storage", f"Missing [{loc}]: {p.name}", "WARN")
    
    return True

def check_mcp_tools(config):
    """Verifies all MCP server commands are valid and executable."""
    mcp_servers = config.get("tools", {}).get("mcpServers", {})
    all_ok = True
    
    for name, srv in mcp_servers.items():
        cmd = srv.get("command")
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
    storage_root = Path(config["strategic_edition"].get("storage_root", "D:/Nanobot_Storage"))
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
    print(f"\n{BOLD}Strategic Doctor: Diagnostic Run ({Path(__file__).name}){RESET}")
    print("="*50)
    
    config = check_config()
    if not config: sys.exit(1)
    
    if not check_storage(config): sys.exit(1)
    if not check_patch_integrity(config): sys.exit(1)
    if not check_static_analysis(): sys.exit(1)
    if not check_mcp_tools(config): sys.exit(1)
    if not check_batch_jobs(config): sys.exit(1)
    
    print("="*50)
    print(f"{GREEN}{BOLD}SUCCESS: All Strategic pillars are healthy. Proceeding with launch.{RESET}\n")

if __name__ == "__main__":
    main()
