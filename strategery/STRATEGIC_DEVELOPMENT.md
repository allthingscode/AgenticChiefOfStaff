# Nanobot Strategic Edition: Development & Maintenance Guide

This document serves as the primary technical "Source of Truth" for AI agents and developers maintaining the Nanobot Strategic Edition. It outlines the architectural boundaries, security mandates, and standard operating procedures (SOPs) required to ensure system integrity.

## 🛡️ Architectural Mandates (Hard Mandates)

### 1. Zero Core Pollution
- **Mandate:** NEVER modify files in the `nanobot/` directory.
- **Implementation:** All custom logic must reside in `strategery/patches/` or be implemented as runtime monkey-patches in `strategic_launcher.py`. This ensures seamless synchronization with upstream updates.

### 2. Logic Isolation
- **Mandate:** Refactor the "brains" of any patch (formatting, parsing, utility logic) into standalone pure functions within the `strategery/logic/` module.
- **Goal:** Ensure 100% unit test coverage for strategic logic without dependencies on the core Nanobot codebase.

### 3. Config Integrity & BOM Handling
- **Mandate:** Preserve JSON readability and Windows compatibility.
- **Rules:** 
  - Use 4-space indentation and multi-line formatting.
  - Files must be encoded as UTF-8. 
  - For Windows compatibility, `config.json` should be handled as `utf-8-sig` (BOM) during read/write to prevent Pydantic validation errors.

### 4. Patch Interface (F-018)
- **Mandate:** Every strategic patch MUST use the `PatchContext` object handed to its `apply()` method.
- **Restriction:** Never manually import `STORAGE_ROOT` or `RAW_CONFIG` inside a patch; use `context.storage_root` and `context.config` instead.

### 5. Strict Symbol Guard (F-025)
- **Mandate:** All patches targeting core Nanobot code MUST define `required_symbols`. 
- **Goal:** Ensures the bot fails fast if an upstream update changes core logic signatures, preventing silent regressions.

---

## 🗺️ System Map & Pathing

Strategic Edition operates across a dual-drive architecture. All tools and agents MUST use the following generalized paths:

| Domain | Logical Path | Description |
|---|---|---|
| **Project Root** | `<PROJECT_ROOT>` | Source code, patches, and repository files. |
| **Storage Root** | `D:\Nanobot_Storage` | The exclusive domain for logs, memory, and sessions. |
| **Logs** | `D:\Nanobot_Storage\logs` | Runtime gateway and strategic diagnostic logs. |
| **Memory** | `D:\Nanobot_Storage\workspace\memory` | ChromaDB (Vector) and SQLite (Keyword) indices. |
| **Sessions** | `D:\Nanobot_Storage\workspace\sessions` | Conversation history and checkpoint files. |

**MANDATE:** All file operations and tool arguments targeting the D: drive MUST use **absolute paths**. Specialists (sub-agents) lose relative context for the storage drive; absolute paths ensure 100% visibility.

---

## ⚙️ The Specialist Economy (Delegation)

To maintain context efficiency and model precision, the system enforces a strict delegation hierarchy:

- **Main Agent (Orchestrator):** Strictly responsible for high-level reasoning and routing. It is FORBIDDEN from calling high-power tools (Google Search, Email, Direct File Access) directly.
- **Specialists (Sub-agents):** Spawned via the `spawn` tool to perform surgical tasks.
    - **Researcher:** Optimized for data retrieval, log audits, and fact-finding.
    - **Architect:** Optimized for code refactoring, system design, and complex implementation.

---

## 🔄 Mandatory Pre-Commit Protocol (SOPs)

Before proposing a commit or finalizing any task, the following steps MUST be executed:

1.  **[SOP-001] Testing:** Run all unit tests: `python -m pytest strategery/tests/unit/`.
2.  **[SOP-002] Strategic Roadmap:** Update `<PROJECT_ROOT>\strategery\STRATEGIC_EDITION.md` to reflect new capabilities (Public-facing only; no internal bug IDs).
3.  **[SOP-003] Privacy Audit:** Verify no hard-coded personal paths (e.g., `C:\Users\...`) or credentials in committed code.
4.  **[SOP-004] Strategic Doctor:** Run the diagnostic suite: `$env:PYTHONPATH="."; <PYTHON_EXE> -m strategery.strategic_doctor` to ensure all strategic pillars are healthy.
5.  **[SOP-005] Live Verification (LEV):** For behavioral changes, provide a "Live Environment Verification" prompt for the user to send to the running instance.

---
*Document Version: 1.0.0 (2026-03-24)*
