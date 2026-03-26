"""
DOCTOR LOGIC: Core recovery and repair functions for the Strategic Doctor.
Mandate: Decouple 'brains' from the CLI tool for 100% testability.
"""
import json
import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from strategery.logic.config_logic import StrategicConfig

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

def check_config_health(config_path: Path) -> Tuple[bool, str, Optional[Any]]:
    """Logic for validating config file health."""
    from strategery.logic.config_logic import validate_strategic_config

    if not config_path.exists():
        return False, f"Missing at {config_path}", None

    try:
        with open(config_path, "rb") as f:
            raw_bytes = f.read()
            has_bom = raw_bytes.startswith(b'\xef\xbb\xbf')

        with open(config_path, "r", encoding="utf-8-sig") as f:
            raw_data = json.load(f)

        config = validate_strategic_config(raw_data)

        if has_bom:
            return True, "UTF-8 BOM detected", config

        return True, "OK", config
    except Exception as e:
        return False, str(e), None

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

def check_storage_health(config: 'StrategicConfig') -> List[Tuple[str, bool, str]]:
    """Logic for auditing storage integrity."""
    storage_root = Path(config.strategic_edition.storage_root)
    checks = []

    # 1. Root existence
    if not storage_root.exists():
        checks.append(("Root", False, f"Missing at {storage_root}"))
        return checks

    # 2. Write tests (BUG-239: Distinguish between Root and Workspace)
    # Subagents frequently fail if they try to write to root.

    # Root Test
    test_root = storage_root / ".doctor_root_test"
    try:
        test_root.write_text("health_check")
        test_root.unlink()
        checks.append(("RootWrite", True, f"Verified on {storage_root.drive}"))
    except Exception as e:
        checks.append(("RootWrite", False, f"Restricted (Expected): {e}"))

    # Workspace Test (CRITICAL for Subagents)
    workspace_dir = storage_root / "workspace"
    test_work = workspace_dir / ".doctor_workspace_test"
    try:
        if not workspace_dir.exists():
            workspace_dir.mkdir(parents=True, exist_ok=True)
        test_work.write_text("health_check")
        test_work.unlink()
        checks.append(("WorkspaceWrite", True, "Verified (Subagents OK)"))
    except Exception as e:
        checks.append(("WorkspaceWrite", False, f"FAILED: Specialists will not be able to function: {e}"))

    # 3. Critical Files
    creds_root = Path.home() / ".nanobot"
    critical = {
        "chroma.sqlite3": storage_root / "workspace" / "memory" / "chroma" / "chroma.sqlite3",
        "checkpoints.db": storage_root / "workspace" / "checkpoints.db",
        "BACKUP_MANIFEST.md": storage_root / "BACKUP_MANIFEST.md",
        "token.json": creds_root / "secrets" / "token.json",
        "credentials.json": creds_root / "google_surgical" / "credentials" / f"{config.strategic_edition.user_email}.json"
    }

    for name, p in critical.items():
        if p.exists():
            if name == "token.json":
                # BUG-236: Deep validation of token health
                try:
                    with open(p, "r") as f:
                        token_data = json.load(f)
                    if not token_data.get("refresh_token"):
                        checks.append((name, False, "MALFORMED (Missing refresh token)"))
                    else:
                        checks.append((name, True, "Found"))
                except Exception as e:
                    checks.append((name, False, f"CORRUPT: {e}"))
            else:
                checks.append((name, True, "Found"))
        else:
            checks.append((name, False, "Missing"))

    return checks

def repair_oauth_token(config: 'StrategicConfig') -> bool:
    """Removes expired/revoked token.json to trigger re-auth (BUG-236)."""
    token_path = Path.home() / ".nanobot" / "secrets" / "token.json"
    if token_path.exists():
        try:
            bak_path = token_path.with_suffix(".json.bak")
            if bak_path.exists(): bak_path.unlink()
            token_path.rename(bak_path)
            return True
        except:
            return False
    return False

def check_mcp_health(config: 'StrategicConfig') -> List[Tuple[str, bool, str]]:
    """Logic for verifying MCP server executables."""
    results = []
    mcp_servers = config.tools.mcp_servers

    for name, srv in mcp_servers.items():
        cmd = srv.command
        if not cmd: continue
        if shutil.which(cmd) or Path(cmd).exists():
            results.append((name, True, f"Verified: {Path(cmd).name}"))
        else:
            results.append((name, False, f"Not found: {cmd}"))
    return results

def check_batch_health(config: 'StrategicConfig') -> List[Tuple[str, bool, str]]:
    """Logic for validating batch job metadata."""
    storage_root = Path(config.strategic_edition.storage_root)
    items_dir = storage_root / "workspace" / "cron" / "items"
    results = []

    if not items_dir.exists():
        return results

    for md_file in items_dir.glob("*.md"):
        try:
            content = md_file.read_text(encoding="utf-8-sig")
            if not content.strip().startswith("---"):
                results.append((md_file.name, False, "Missing front-matter"))
                continue

            meta = {}
            for line in content.split("---")[1].splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip()] = v.strip()

            required = ["id", "schedule", "specialist"]
            missing = [k for k in required if k not in meta]
            if missing:
                results.append((md_file.name, False, f"Missing: {missing}"))
            else:
                results.append((meta['id'], True, "Verified"))
        except Exception as e:
            results.append((md_file.name, False, str(e)))
    return results

def check_linter_health(apply: bool = False) -> List[Tuple[str, bool, str]]:
    """Logic for static analysis of strategic files. Uses ruff if available, otherwise basic compile."""
    strat_dir = Path(__file__).parent.parent
    targets = list((strat_dir / "patches").glob("*.py")) + list(strat_dir.glob("*.py"))
    results = []

    # 1. Try Ruff first (High Performance)
    ruff_bin = shutil.which("ruff")
    if ruff_bin:
        try:
            # If apply=True, try to auto-fix first
            if apply:
                subprocess.run([ruff_bin, "check", str(strat_dir), "--fix", "--select", "E,F,B", "--no-cache"],
                               capture_output=True, text=True)
                results.append(("Ruff Fix", True, "Attempted auto-fixes for fixable linting issues."))

            # MANDATE: Only block on CRITICAL errors (F=Pyflakes, E9=Syntax, B9=Bugbear critical)
            # We treat E501 (Line Length) and others as warnings.
            critical_cmd = [ruff_bin, "check", str(strat_dir), "--select", "F,E9,B9", "--no-cache"]
            critical_proc = subprocess.run(critical_cmd, capture_output=True, text=True, encoding="utf-8")

            if critical_proc.returncode != 0:
                results.append(("Ruff Critical", False, f"CRITICAL issues detected (startup blocked):\n{critical_proc.stdout}"))
                return results # Block startup

            # Secondary pass for non-critical warnings
            warn_cmd = [ruff_bin, "check", str(strat_dir), "--select", "E,B", "--ignore", "E501", "--no-cache"]
            warn_proc = subprocess.run(warn_cmd, capture_output=True, text=True, encoding="utf-8")

            if warn_proc.returncode == 0:
                results.append(("Ruff Audit", True, "All strategic files passed analysis."))
            else:
                # We return True (Success) but include the warning message
                results.append(("Ruff Audit", True, f"Non-critical warnings detected:\n{warn_proc.stdout}"))

            return results
        except Exception as e:
            results.append(("Ruff", False, f"Ruff execution failed: {e}"))

    # 2. Fallback to basic compilation
    for py_file in targets:
        try:
            with open(py_file, "r", encoding="utf-8-sig") as f:
                content = f.read()
            compile(content, str(py_file), 'exec')
            results.append((py_file.name, True, "Syntax OK (Fallback)"))
        except SyntaxError as se:
            results.append((py_file.name, False, f"Syntax ERROR: {se}"))
        except Exception as e:
            results.append((py_file.name, False, f"Analysis error: {e}"))
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
        from strategery.logic.checkpoint_logic import CheckpointStore
        CheckpointStore(db_path=str(db_path))
        return True
    except Exception:
        return False
