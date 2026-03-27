# Nanobot Strategic Edition — Claude Code Context

> **📢 Project Status: Maintenance Mode (Reference Only)**
> 
> The Python Nanobot Strategic Edition is in **stabilization mode**. It serves as a high-fidelity "Golden Reference" for the next-generation **compiled Golang architecture**. Focus on reliability and documentation accuracy.

## Project Overview

**nanobot** is an ultra-lightweight personal AI agent framework. This repo contains the upstream nanobot core plus the **Strategic Edition** overlay — a set of runtime monkey-patches that live entirely in `strategery/` with zero modification to core nanobot files.

- **Core**: `nanobot/` — upstream, never modified directly
- **Overlay**: `strategery/` — all custom logic, patches, tools, tests
- **Storage**: `D:\Nanobot_Storage\` — all runtime data, logs, workspace
- **Python**: `nanoClaw/Scripts/python.exe` — always use this, never bare `python`

## Hard Mandates

- **Zero Core Pollution**: NEVER edit files in `nanobot/`. All changes go in `strategery/patches/` as runtime monkey-patches or `strategery/logic/` as pure functions.
- **Zero Drive-Root Writes**: Subagents must write to `D:\Nanobot_Storage\workspace\`, never to `C:\` or `D:\` roots.
- **Logic Isolation**: "Brain" logic in `strategery/logic/` (pure, testable); "Bridge" patches in `strategery/patches/` (thin wrappers only).
- **Patch Interface**: Every patch receives a `PatchContext` object in `apply()`. Never import `STORAGE_ROOT` or raw config inside a patch — use `context.storage_root` and `context.config`.
- **Symbol Guards**: All patches must define `required_symbols` to fail fast on upstream API changes.
- **Private files gitignored**: `strategery/private/` is never committed. Contains bug backlog, feature backlog, personas, and agent memories.

## Key Paths

| Purpose | Path |
|---------|------|
| Python executable | `nanoClaw/Scripts/python.exe` |
| Unit tests | `strategery/tests/unit/` |
| Logs (runtime) | `D:\Nanobot_Storage\logs\` |
| Workspace | `D:\Nanobot_Storage\workspace\` |
| Bug backlog | `strategery/private/BUG_BACKLOG.md` |
| Feature backlog | `strategery/private/FEATURE_BACKLOG.md` |
| Agent mandates | `strategery/private/gemini.md` |
| Public feature doc | `strategery/STRATEGIC_EDITION.md` |

## Common Commands

```powershell
# Run unit tests
nanoClaw/Scripts/python.exe -m pytest strategery/tests/unit/ -q

# Run strategic doctor
$env:PYTHONPATH="."; nanoClaw/Scripts/python.exe -m strategery.strategic_doctor

# Run specific test file
nanoClaw/Scripts/python.exe -m pytest strategery/tests/unit/test_<name>.py -v
```

## Pre-Commit SOPs (run before every commit)

1. **[SOP-001]** `nanoClaw/Scripts/python.exe -m pytest strategery/tests/unit/` — 100% pass required
2. **[SOP-005]** Privacy audit — no hardcoded `C:\Users\...` paths or credentials in committed code
3. **[SOP-006]** Strategic Doctor — `nanoClaw/Scripts/python.exe -m strategery.strategic_doctor`
4. **[SOP-010]** Bug-fix lockdown — never mark a bug fixed without a reproducing test

The pre-commit hook (`strategic_guard.py`) runs SOP-000 (ruff), SOP-001 (tests), SOP-003 (privacy), and SOP-004 (doctor) automatically.

## Architecture Notes

- **Specialist Economy**: Main agent delegates to `researcher` and `architect` subagents via `spawn`. Main agent is blocked from surgical tools (calendar, tasks, drive, email, search).
- **VectorStoreFactory**: Always use `VectorStoreFactory.get_store()` — never import `StrategicVectorStore` directly.
- **Lifecycle hooks**: Register cleanup via `lifecycle_manager.register_shutdown_hook()`.
- **Async standard**: Use `asyncio.get_running_loop()` in `try/except RuntimeError`. Never `get_event_loop()`.
- **Windows encoding**: All scripts use `PYTHONUTF8=1` or `-X utf8`. Strategic logger has `UnicodeSafeStreamHandler`.

## Specialist Models (from config.json)

| Role | Model |
|------|-------|
| Default (main agent) | `gemini-3-flash-preview` |
| Researcher | `gemini-2.5-flash-lite` |
| Architect | `gemini-3-pro-preview` |

## What NOT to commit

- `strategery/private/` (gitignored)
- `D:\Nanobot_Storage\` contents
- Hardcoded credentials or personal paths
- Internal bug IDs in `strategery/STRATEGIC_EDITION.md` (public-facing only)
