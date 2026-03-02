# Nanobot Strategic Edition

## **Overview**
The Strategic Edition is a modular, high-performance extension of the Nanobot Core, specifically designed for deep integration with senior-level productivity workflows. It focuses on **Zero Core Pollution**, **Semantic Recall**, and **Surgical Tooling**.

## **Latest Version: 2026-03-01 (Stabilized)**

### **1. Semantic Memory (RAG)**
- **Vector Database:** Uses **ChromaDB** as a local-first singleton for long-term durable recall.
- **Modern Embeddings:** Integrated with the modern `google-genai` library using **`models/gemini-embedding-001`** (3072 dimensions).
- **Proactive Warmup:** Initialized at startup to eliminate the 3-second "Cold Start" delay on first message.

### **2. "Clean History" Consolidation**
- **Bloat Prevention:** Retired the linear `HISTORY.md` file in favor of the Vector Store.
- **Surgical Ingestion:** Summaries and memory updates are automatically vectorized during consolidation.
- **Daily Journals:** Chronological journals (e.g., `2026-03-01.md`) provide human-readable snapshots without context window bloat.

### **3. Advanced Telegram Integration**
- **Topic/Thread Awareness:** Full support for Telegram Topics (sessions map correctly to thread IDs).
- **Duplicate Fix:** Fixed the logic bug that caused double-processing in threaded sessions.
- **Media Redirection:** Automatically redirects all media (photos, voice, documents) to your local `D:/Nanobot_Storage/workspace/media` directory.

### **4. Infrastructure & Resilience**
- **Unified CLI Wrapper:** The `nanobot.cmd` script in the project root enforces all strategic patches across ALL commands (e.g., `nanobot status`, `nanobot gateway`).
- **Self-Awareness Context:** Tracks environmental changes and architectural updates in `D:\Nanobot_Storage\workspace\memory\STRATEGIC_CONTEXT.md` to keep the agent informed of its own state.
- **BOM Safety:** Global monkey-patch for `builtins.open` ensures all JSON/JSONL files are read with `utf-8-sig` on Windows.
- **Signal Handling:** Hardened signal and loop retrieval for multi-threaded environments.
- **Modular Patching:** 100% of strategic logic is contained in `strategery/patches/`, ensuring zero impact on upstream `nanobot/` core.

## **TODO: Next Horizon**
- [ ] **Knowledge Graph:** Implement relationship-based memory beyond basic semantic similarity.
- [ ] **Cross-Device Sync:** Explore cloud-syncing for the ChromaDB database.
- [ ] **Surgical UI:** Add a slim dashboard for managing "Gold Standard" facts in `MEMORY.md`.
