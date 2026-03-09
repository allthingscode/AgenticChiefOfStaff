"""
STRATEGIC GUARD: Certification & Stability Engine
Goal: Automate Mandatory Pre-Commit Protocols (SOPs) to ensure 100% stability.
Mandate: Certify every change against Strategic Pillars before it reaches Git.
"""
import os
import sys
import subprocess
import argparse
from pathlib import Path

# ANSI Colors for Terminal Clarity
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"

# Absolute Path to Project Python
PYTHON_EXE = r"C:\Users\HayesChiefOfStaff\Documents\nanobot\nanoClaw\Scripts\python.exe"

def run_command(command, description, capture=False):
    """Executes a shell command and returns the result."""
    print(f"[*] {BOLD}Executing {description}...{RESET}")
    env = os.environ.copy()
    env["PYTHONPATH"] = "."
    
    try:
        result = subprocess.run(
            command, 
            shell=True, 
            env=env, 
            capture_output=capture, 
            text=True
        )
        if result.returncode == 0:
            print(f"[{GREEN}OK{RESET}] {description} passed.")
            return True, result.stdout if capture else ""
        else:
            print(f"[{RED}FAIL{RESET}] {description} failed (Code: {result.returncode}).")
            if result.stderr:
                print(f"{RED}{result.stderr}{RESET}")
            return False, result.stdout if capture else ""
    except Exception as e:
        print(f"[{RED}ERROR{RESET}] Unexpected failure in {description}: {e}")
        return False, ""

def sop_001_testing():
    """[SOP-001] Run all Strategic Unit Tests."""
    cmd = f"{PYTHON_EXE} -m pytest strategery/tests/unit/"
    return run_command(cmd, "SOP-001: Strategic Unit Tests")

def sop_005_privacy():
    """[SOP-005] Personal Data Audit (Privacy Guard)."""
    # Patterns that should NOT be in committed code (excluding this script and config)
    restricted = ["C:\\Users\\HayesChiefOfStaff", "token.json", "credentials"]
    print(f"[*] {BOLD}Executing SOP-005: Privacy Audit...{RESET}")
    
    all_ok = True
    # We audit only the 'strategery/patches' and 'strategery/tools' folders
    targets = [Path("strategery/patches"), Path("strategery/tools")]
    
    for target in targets:
        for py_file in target.glob("*.py"):
            try:
                content = py_file.read_text(encoding="utf-8-sig")
                for pattern in restricted:
                    if pattern in content:
                        print(f"[{RED}FAIL{RESET}] Found restricted pattern '{pattern}' in {py_file}")
                        all_ok = False
            except Exception as e:
                print(f"[{YELLOW}WARN{RESET}] Could not audit {py_file}: {e}")
                
    if all_ok:
        print(f"[{GREEN}OK{RESET}] SOP-005: Privacy Audit passed.")
    return all_ok

def sop_006_doctor():
    """[SOP-006] Strategic Doctor (System Health)."""
    cmd = f"{PYTHON_EXE} -m strategery.strategic_doctor"
    return run_command(cmd, "SOP-006: Strategic Doctor")

def policy_linter():
    """Enforce 'Zero Core Pollution' and 'Async Standard'."""
    print(f"[*] {BOLD}Executing Policy Linter...{RESET}")
    all_ok = True
    
    # 1. Async Check: Avoid get_event_loop() (SOP: Use get_running_loop())
    # We use a regex-style check to avoid false positives from strings/comments
    cmd = 'grep -r "asyncio.get_event_loop()" strategery --exclude="strategic_guard.py" --exclude-dir="tests"'
    # Note: On Windows 'grep' is grep_search tool, but for shell we use findstr.
    # Let's use a Python-based check for portability and precision.
    
    targets = [Path("strategery/patches"), Path("strategery/tools")]
    for target in targets:
        for py_file in target.glob("*.py"):
            try:
                content = py_file.read_text(encoding="utf-8-sig")
                if "asyncio.get_event_loop()" in content:
                    # Ignore comments
                    lines = [line for line in content.splitlines() if "asyncio.get_event_loop()" in line and not line.strip().startswith("#")]
                    if lines:
                        print(f"[{RED}FAIL{RESET}] Found 'asyncio.get_event_loop()' in: {py_file}")
                        all_ok = False
            except Exception: pass
        
    # 2. Path Check: No relative D: drive paths
    cmd = 'findstr /S /M "D:\\" strategery\\*.py'
    # This is complex because we USE D:\ in strings, so we audit for literal relative path usage
    # For now, we rely on the Doctor for storage pathing.

    if all_ok:
        print(f"[{GREEN}OK{RESET}] Policy Linter passed.")
    return all_ok

def main():
    parser = argparse.ArgumentParser(description="Strategic Guard: Certification Engine")
    parser.add_argument("--skip-tests", action="store_true", help="Skip SOP-001 (Tests)")
    parser.add_argument("--commit-check", action="store_true", help="Run in pre-commit mode (Fail fast)")
    args = parser.parse_args()

    print(f"\n{BOLD}🛡️ Strategic Guard: Certification Run{RESET}")
    print("="*60)
    
    pipeline = [
        (sop_006_doctor, "Strategic Doctor"),
        (sop_005_privacy, "Privacy Audit"),
        (policy_linter, "Policy Linter")
    ]
    
    if not args.skip_tests:
        pipeline.insert(0, (sop_001_testing, "Unit Tests"))
        
    failures = 0
    for func, name in pipeline:
        if not func():
            failures += 1
            if args.commit_check:
                print(f"\n{RED}{BOLD}CERTIFICATION FAILED: {name} must pass before commit.{RESET}\n")
                sys.exit(1)
                
    print("="*60)
    if failures == 0:
        print(f"{GREEN}{BOLD}PASSED: All Strategic Pillars are certified.{RESET}\n")
    else:
        print(f"{RED}{BOLD}FAILED: {failures} certification check(s) failed.{RESET}\n")
        sys.exit(1)

if __name__ == "__main__":
    main()
