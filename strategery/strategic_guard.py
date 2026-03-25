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

# MANDATE: Use dynamic resolution for the project's Python executable.
PROJECT_ROOT = Path(__file__).parent.parent.absolute()
PYTHON_EXE = str(PROJECT_ROOT / "nanoClaw" / "Scripts" / "python.exe")
if not Path(PYTHON_EXE).exists():
    PYTHON_EXE = sys.executable

def run_command(command, description, capture=False):
    """Executes a shell command and returns the result."""
    print(f"[*] {BOLD}Executing {description}...{RESET}")
    env = os.environ.copy()
    env["PYTHONPATH"] = "."
    
    try:
        # Check if the command is ruff to avoid shell=True if possible, 
        # but for consistency with existing code, we use shell=True.
        result = subprocess.run(
            command, 
            shell=True, 
            env=env, 
            capture_output=True, # Always capture for ruff to show errors
            text=True
        )
        if result.returncode == 0:
            print(f"[{GREEN}OK{RESET}] {description} passed.")
            return True, result.stdout
        else:
            print(f"[{RED}FAIL{RESET}] {description} failed (Code: {result.returncode}).")
            if result.stdout: print(result.stdout)
            if result.stderr: print(f"{RED}{result.stderr}{RESET}")
            return False, result.stdout
    except Exception as e:
        print(f"[{RED}ERROR{RESET}] Unexpected failure in {description}: {e}")
        return False, ""

def sop_000_speed_analysis():
    """[SOP-000] High-Speed Linting (Ruff)."""
    import shutil
    ruff_bin = shutil.which("ruff")
    if not ruff_bin:
        print(f"[{YELLOW}WARN{RESET}] ruff not found. Skipping SOP-000.")
        return True # Soft fail if not installed
    
    cmd = f"{ruff_bin} check . --select E,F,B --ignore E501 --no-cache"
    return run_command(cmd, "SOP-000: Speed Analysis (ruff)")[0]

def sop_001_testing():
    """[SOP-001] Run all Strategic Unit Tests."""
    cmd = f"{PYTHON_EXE} -m pytest strategery/tests/unit/"
    return run_command(cmd, "SOP-001: Strategic Unit Tests")[0]

def sop_003_privacy():
    """[SOP-003] Personal Data Audit (Privacy Guard)."""
    # Patterns that should NOT be in committed code (excluding this script and config)
    restricted = ["C:\\Users\\HayesChiefOfStaff", "token.json", "credentials"]
    print(f"[*] {BOLD}Executing SOP-003: Privacy Audit...{RESET}")
    
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
        print(f"[{GREEN}OK{RESET}] SOP-003: Privacy Audit passed.")
    return all_ok

def sop_004_doctor():
    """[SOP-004] Strategic Doctor (System Health)."""
    cmd = f"{PYTHON_EXE} -m strategery.strategic_doctor"
    return run_command(cmd, "SOP-004: Strategic Doctor")[0]

def policy_linter():
    """Enforce 'Zero Core Pollution' and 'Async Standard'."""
    print(f"[*] {BOLD}Executing Policy Linter...{RESET}")
    all_ok = True
    
    # 1. Async Check: Avoid get_event_loop() (SOP: Use get_running_loop())
    # We use a regex-style check to avoid false positives from strings/comments
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
        (sop_000_speed_analysis, "Speed Analysis"),
        (sop_004_doctor, "Strategic Doctor"),
        (sop_003_privacy, "Privacy Audit"),
        (policy_linter, "Policy Linter")
    ]
    
    if not args.skip_tests:
        # Move unit tests after the fast checks
        pipeline.append((sop_001_testing, "Unit Tests"))
        
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
