# Nanobot Strategic Edition: Development & Maintenance Guide

> **📢 Project Status: Maintenance Mode (Reference Only)**
> 
> This Python-based implementation of Nanobot Strategic Edition is now in **maintenance mode**. It serves as a high-fidelity "Golden Reference" for the next-generation **compiled Golang architecture**. Active development has shifted to the Go repository; this codebase remains as the authoritative reference for architectural boundaries, security mandates, and SOPs during the transition.

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

### 6. Transition-First Mandate (EPIC-001)
- **Mandate:** To minimize technical debt during the Golang transition, any new high-complexity features or fragile I/O tools must be prioritized for implementation in Go (via the gRPC Bridge) rather than expanding the Python codebase.
- **Goal:** Focus Python work on stabilization and the transition handshake.

---

## 🚀 Golden Reference: Architectural Innovations

These innovations represent the "Surgical DNA" of the Strategic Edition. Porting these to the Golang architecture is a high-priority mandate.

### 1. Rubric-Driven Reflection (Generator-Critic-Refiner)
- **Concept:** A specialist agent generates a JSON success rubric before execution. Its output is then audited by a separate "Critic" turn against that rubric.
- **Value:** Eliminates 90% of model hallucinations and instruction-following failures.
- **Reference:** `strategery/logic/reflection_logic.py`

### 2. Hybrid Memory Index (Semantic + Keyword)
- **Concept:** Combines ChromaDB (Vector) for semantic recall with SQLite FTS5 (Keyword) for precise identifier matching.
- **Value:** Vector search often fails on technical strings (BUG IDs, UUIDs); keyword search ensures 100% precision for technical data.
- **Reference:** `strategery/patches/hybrid_store.py`

### 3. Silent Spawning & Turn Suppression
- **Concept:** Suppresses the Main Agent's intermediate thoughts/hallucinations during a `spawn` call.
- **Value:** User only sees the final, atomic result of the delegation, resulting in a cleaner, professional-grade interface.
- **Reference:** `strategery/patches/loop.py`

### 4. Stateless Shell & Command Hardening
- **Concept:** A translation engine that converts POSIX-style shell commands into Windows-safe PowerShell, handling spaces and drive root redirects.
- **Value:** Bridges the gap between "Unix-trained" LLMs and real-world Windows environments.
- **Reference:** `strategery/logic/subagent_logic.py` (`harden_subagent_command`)

### 5. Environmental Awareness Injection
- **Concept:** Generates a real-time system manifest (`AWARENESS.md`) at launch and injects it into the system prompt.
- **Value:** Prevents redundant informational tool calls; the agent "just knows" its current OS, paths, and date.
- **Reference:** `strategery/patches/awareness.py`

### 6. Triple-Lock Stability Patching
- **Concept:** A three-layer patching strategy (Class, Instance, and Global utility) for pre-initialized Windows objects.
- **Value:** Ensures that strategic upgrades stick even if objects were instantiated before the strategic launcher started.
- **Reference:** `strategery/patches/telegram.py`

### 7. Memory Consolidation (F-015: The Soul Engine)
- **Concept:** Periodically compresses conversation history into a permanent "Fact Sheet" (SOUL) and a chronological "History Entry" (Journal).
- **Value:** Prevents context window exhaustion while ensuring that critical facts (project IDs, user preferences) are never forgotten.
- **Reference:** `strategery/patches/memory.py`

### 8. Journal-Based Continuity (F-022: Daily Awareness)
- **Concept:** Automatically injects a "State of Play" snippet from the Daily Journal into every turn.
- **Value:** Provides the agent with seamless awareness of events that occurred earlier in the day, even if the current session history has been pruned or cleared.
- **Reference:** `strategery/logic/memory_logic.py` (`get_journal_continuity`)

---

## 🛠️ The Mechanical DNA: Implementation Specifics for Go

These "hidden" behaviors are critical to the stability and precision of the Strategic Edition. Failure to port these mechanical nuances will result in regressions (e.g., shell failures, model hallucinations, or data corruption).

### 1. Shell Hardening & Translation (BUG-225/227/228)
- **POSIX-to-PowerShell:** LLMs frequently output `&&` or `||` for command chaining. PowerShell 5.1 (standard on Windows) does not support these. The system MUST translate them to `;` for sequential execution.
- **Stateless Shell Mandate (BUG-246):** The `exec` tool is entirely stateless. `cd` commands are effectively ignored across turns. The system enforces **Absolute Paths** for all operations.
- **Drive-Blindness Override (BUG-228/240):** Models often hallucinate paths on `C:\`. The hardening logic automatically redirects these to the mandated `D:\Nanobot_Storage\workspace` root.
- **Script Auto-Execution (BUG-243):** Standalone calls to `.ps1` files are automatically wrapped in `powershell -NoProfile -ExecutionPolicy Bypass -File "..."` to ensure they execute correctly.
- **CLI-XML Stripping (BUG-247):** PowerShell's `stderr` is often wrapped in verbose CLIXML. The system implements a dedicated `strip_clixml` parser to extract the raw, human-readable error message.

### 2. High-Fidelity Content Scrubbing
- **Reasoning Artifact Stripping:** To prevent context "echoing" and model confusion, all internal reasoning tags (`<thought>`, `<think>`, etc.) and markdown-style "Thinking" headers are aggressively stripped from logs and subagent handovers.
- **Idle Loop Prevention:** If a model returns *only* reasoning without tool calls or final content, the system injects a "Mandate Nudge" to force execution instead of allowing an infinite thought loop.

### 3. Precision Memory Mechanics (FTS5)
- **Identifier Quoting:** In SQLite FTS5, hyphens (e.g., `BUG-042`) are treated as `NOT` operators. All memory queries MUST be double-quoted (`"BUG-042"`) to ensure precise technical retrieval.
- **BM25 Ranking:** Uses the FTS5 BM25 ranking algorithm, prioritizing keyword matches over semantic vector results to ensure "Exact Match" identifiers take precedence.

### 4. Windows-Specific I/O
- **BOM Management (utf-8-sig):** All `config.json` and `.jsonl` files MUST be handled with `utf-8-sig` (Byte Order Mark). Without the BOM, Pydantic and other Windows-based parsers may fail on certain characters or file starts.
- **Lifecycle Resilience:** To prevent `closed loop` or `access denied` errors on Windows, all cleanup tasks (closing DBs, flushing logs) must be registered via a central `lifecycle_manager` and executed during a clean shutdown hook.

### 5. Multimodal Handover (ARCH-022)
- **Atomic Manifest Injection:** Specialists do not "search" for images. Instead, the Orchestrator injects an **Atomic Manifest** containing the ID, Absolute Path, and Description of any attachments directly into the Specialist's system prompt.

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

1.  **[SOP-000] Speed Analysis:** Run high-speed linting: `ruff check .`. All syntax and logic violations must be resolved or auto-healed via `ruff check . --fix`.
2.  **[SOP-001] Testing:** Run all unit tests: `python -m pytest strategery/tests/unit/`.
3.  **[SOP-002] Strategic Roadmap:** Update `<PROJECT_ROOT>\strategery\STRATEGIC_EDITION.md` to reflect new capabilities (Public-facing only; no internal bug IDs).
4.  **[SOP-003] Privacy Audit:** Verify no hard-coded personal paths (e.g., `C:\Users\...`) or credentials in committed code.
5.  **[SOP-004] Strategic Doctor:** Run the diagnostic suite: `$env:PYTHONPATH="."; <PYTHON_EXE> -m strategery.strategic_doctor` to ensure all strategic pillars are healthy.
6.  **[SOP-005] Live Verification (LEV):** For behavioral changes, provide a "Live Environment Verification" prompt for the user to send to the running instance.
7.  **[SOP-012] Parity Verification (Go Transition):** When porting logic or tools to Golang, the new implementation MUST pass the identical behavioral test suite used by the original Python version. No component is certified for production until 1:1 behavioral parity is verified.

---
*Document Version: 1.0.0 (2026-03-24)*
