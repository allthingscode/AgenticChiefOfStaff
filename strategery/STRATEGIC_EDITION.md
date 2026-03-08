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
- **Orchestrator Synthesis:** A specialized report protocol ensures the Main Agent only synthesizes specialist findings rather than re-verifying them, preserving turn efficiency.

## **3. Autonomous Batch Operations**
A unique automation layer that operates independently of real-time user interaction:
- **Modular Task Loader:** Dynamic, folder-based task definitions (`.md` files) allow for complex maintenance and reporting routines without modifying core configuration.
- **Self-Correcting Schedules:** A strategic runtime patch enables automated schedule reloading and state preservation across system restarts.
- **Routable Batch Delivery:** Batch results are dynamically redirected to the most recent active user channel (e.g., Telegram), ensuring background tasks remain visible.

## **4. Infrastructure & Resilience**
Optimized for stable long-term operation on Windows environments:
- **Zero Core Pollution:** 100% of strategic logic is applied via runtime monkey-patches and wrappers, ensuring seamless synchronization with upstream core updates.
- **Concurrent Agent Loop:** Replaces global locking with high-performance per-session locks, enabling simultaneous multi-user processing.
- **Non-Blocking Persistence:** Asynchronous session saving offloads I/O to thread pools, eliminating latency spikes during large history saves.
- **Universal Provider Resilience:** Global base-class patching provides unified embedding access, Unicode-safe logging, and automated transient error recovery (exponential backoff) across all AI providers.
- **Strategic Doctor (Pre-Flight Diagnostics):** Automated diagnostic engine (`strategic_doctor.py`) integrated into the launch sequence. Validates configuration, storage access, MCP tool connectivity, and batch job metadata before every start to prevent silent failures.
- **Communication Fallbacks:** Automated disk-based logging for critical notifications ensures data persistence even during API or credential outages.
- **Cloud-First Backup (F-014):** Automated, off-site redundancy on Google Drive with intelligent filtering and automated rotation. Managed via a **Disaster Recovery Manifest** that includes the `.gemini` brain, root launchers, and `.env` credentials to ensure 100% recovery on a new device.

## **5. Strategic Stability Framework (Resilience Phase)**
A dedicated "Self-Healing" pre-flight engine (the Strategic Doctor) that guards against regressions and environmental drift before every system launch:
- **Active Patch Integrity Verification:** The Strategic Doctor programmatically verifies the functional "handshake" between modular patches and the Nanobot core, ensuring monkey-patches are active and functionally correct.
- **Specialist Heartbeat Monitor:** Background monitoring detects and warns of "Ghost" subagents, preventing silent hangs and ensuring high-availability orchestration.
- **No-NameError Shield:** Static syntax analysis across all strategic files catches syntax and import errors before they impact the production gateway.
- **Win32 Headless Safety:** Fully automated, non-GUI health checks are enforced via direct Python execution, bypassing Windows Shell "Open With" triggers for 100% headless reliability.

## **6. NanoGraph Semantic Overlay**
Augments standard memory with a semantic graph overlay for complex relationship-based recall, enabling the agent to navigate memory nodes via explicit entity connections (e.g., 'Project X' -- 'uses' --> 'Technology Y').
