# Nanobot Strategic Edition

## **Architectural Overview**
The Strategic Edition is a modular extension of the Nanobot Core, architected for high-precision senior productivity. It differentiates itself from upstream Nanobot AI through three core pillars: **Zero Core Pollution**, **Hybrid Memory Integrity**, and a **Specialist-Driven Economy**.

---

## **1. Hybrid Memory Architecture (RAG+)**
Unlike the standard linear history or simple vector search in core Nanobot, the Strategic Edition implements a multi-layered recall system:
- **Hybrid Index:** Simultaneous **SQLite FTS5 (Keyword)** and **ChromaDB (Vector)** search ensures 100% precision on technical IDs (e.g., project codes, bug IDs) while maintaining high-recall semantic search.
- **Chronological Continuity (Rolling Journals):** Automatically injects the most recent daily journal snapshots into the prompt, providing the agent with seamless session-to-session awareness.
- **Active RAG:** Specialist subagents utilize a dedicated `search_memory` tool for proactive, deep-dive retrieval beyond the immediate context window.
- **High-Density Consolidation:** Linear history is aggressively summarized and vectorized into the "Source of Truth" to prevent context bloat.

## **2. Specialist Economy & Delegation**
The Strategic Edition enforces a strict hierarchy to maximize model efficiency and cost-effectiveness:
- **Enforced Delegation:** The Main Agent (Orchestrator) is hard-blocked from executing high-power surgical tools (Google, AI Search, Email), mandating the use of Specialists.
- **Role-Based Isolation:** Specialists are strictly routed by role (**'researcher'** vs **'architect'**) with automated model assignment (e.g., Flash-Lite for research, Pro for architecture).
- **Hardened Path Awareness:** Specialist subagents are equipped with explicit mandates for absolute path discovery and recursive storage audits, eliminating "Storage Depth Blindness."
- **High-Fidelity Telemetry:** The system provides real-time visibility into the Agent's reasoning, tool arguments, and results for both the Main Agent and Specialists, formatted for human scanability.

## **3. Autonomous Batch Operations**
A unique automation layer that operates independently of real-time user interaction:
- **Modular Task Loader:** Dynamic, folder-based task definitions (`.md` files) allow for complex maintenance and reporting routines without modifying core configuration.
- **Master Strategic Orchestrator:** A single master task scheduled for 3 AM handles all daily health checks, knowledge extraction, and morning briefing synthesis in a synchronous, ordered sequence.
- **Self-Correcting Schedules:** A strategic runtime patch enables automated schedule reloading and state preservation across system restarts.

## **4. Infrastructure & Resilience**
Optimized for stable long-term operation on Windows environments:
- **Zero Core Pollution:** 100% of strategic logic is applied via runtime monkey-patches and wrappers, ensuring seamless synchronization with upstream core updates.
- **Thin Patch Mandate:** Strategic logic is decoupled from runtime shims into a standalone `strategery/logic/` module, ensuring 100% unit-testability and zero-risk refactoring.
- **Concurrent Agent Loop:** Replaces global locking with high-performance per-session locks, enabling simultaneous multi-user processing.
- **Universal Provider Resilience:** Global base-class patching provides unified embedding access, Unicode-safe logging, and automated tier-based **Model Escalation** to bypass safety filter roadblocks.
- **Fail-Fast Symbol Guard:** Proactive pre-patch signature verification ensures the system detects upstream code changes before they cause runtime instability.
- **Strategic Doctor (Pre-Flight Diagnostics):** Explicit application flow and rich `PatchResult` diagnostics validate the system state before every launch.

---

### **Roadmap & Achievement Log**

| Feature | Status | Impact |
|---|---|---|
| **Configuration Schema (F-016)** | **LIVE** | **Stability:** Strict Pydantic-based validation for all strategic configuration keys. |
| **Symbol Guard (F-025)** | **LIVE** | **Resilience:** Proactive detection of upstream incompatibilities before monkey-patching. |
| **Model Escalation** | **LIVE** | **Stability:** Automatic tier-jumping (Lite -> Pro) to bypass safety filter roadblocks. |
| **Modular Nightly Batch** | **COMPLETED** | **Master Orchestrator:** Single master task scheduled for 3 AM handles all health, extraction, and reporting. |
| **The Thin Patch Mandate** | **COMPLETED** | **Stability:** Decoupled strategic logic from runtime shims for 100% testability and zero-risk refactoring. |
| **High-Fidelity Telemetry** | **LIVE** | **Observability:** Real-time visibility into thoughts, tool arguments, and result snippets across all agents. |
| **Environment Hardening** | **LIVE** | **Stability:** Absolute venv enforcement, forced UTF-8 shells, and nested call resilience for specialists. |
| **Path Processing Resilience** | **LIVE** | **Resilience:** Hardened command-line path processing and synchronized specialist mandates for absolute behavioral compliance. |
| **Surgical Shell Orchestration** | **LIVE** | **Resilience:** Corrected PowerShell quote escaping and implemented shell nesting detection to prevent path mangling (BUG-174/175). |
| **Robust Specialist Navigation** | **LIVE** | **Stability:** Hardened directory listing for Windows roots and eliminated log-audit hallucinations using strict mandates (BUG-178/179/180). |
| **Automated Strategic Discovery** | **LIVE** | **Efficiency:** Injected system metadata manifest that automatically provides specialists with log paths and diagnostic procedures (BUG-181/182). |
| **Finality Mandate** | **LIVE** | **Reliability:** Enforced task completion standards that strictly forbid 'plans' from being reported as results. |
| **NanoGraph Phase 2** | Research | **Intelligence:** Multi-hop reasoning and Personalized PageRank (HippoRAG) for deterministic retrieval. |
| **Readability Reports** | Planning | **UX:** High-readability HTML email templates for 3 AM briefings. |
