# Nanobot Strategic Edition

## **Overview**
The Strategic Edition is a modular, high-performance extension of the Nanobot Core, specifically designed for deep integration with senior-level productivity workflows. It focuses on **Zero Core Pollution**, **Semantic Recall**, and **Surgical Tooling**.

## **Key Features & Differences**

### **1. Semantic Memory (RAG)**
- **Vector Database:** Uses **ChromaDB** as a local-first singleton for long-term durable recall.
- **Modern Embeddings:** Integrated with the modern `google-genai` library using **`models/gemini-embedding-001`** (3072 dimensions).
- **Proactive Warmup:** Initialized at startup to eliminate the 3-second "Cold Start" delay on first message.
- **Hardened RAG:** Selective retrieval skips generic responses to preserve context window for complex queries.
- **Junk Filtering:** Automated filtering of 'No summary available' placeholders from retrieved context before prompt injection.

### **2. "Clean History" Consolidation**
- **Bloat Prevention:** Replaces linear history files with high-density Vector Store summaries.
- **Surgical Ingestion:** Summaries and memory updates are automatically vectorized during consolidation.
- **Daily Journals:** Chronological journals provide human-readable snapshots without context window bloat.

### **3. Advanced Telegram Integration**
- **Topic/Thread Awareness:** Full support for Telegram Topics (sessions map correctly to thread IDs).
- **Redirection Logic:** Automatically redirects all media (photos, voice, documents) to a dedicated local storage directory.

### **4. Infrastructure & Resilience**
- **Unified CLI Wrapper:** The `nanobot.cmd` script in the project root enforces all strategic patches across ALL commands (e.g., `nanobot status`, `nanobot gateway`).
- **Self-Awareness Context:** Tracks environmental changes and architectural updates to keep the agent informed of its own state.
- **BOM Safety:** Global monkey-patch for `builtins.open` ensures all JSON/JSONL files are read correctly on Windows.
- **Signal Handling:** Hardened signal and loop retrieval for multi-threaded environments.
- **Zero Core Pollution:** 100% of strategic logic is contained in `strategery/patches/`, ensuring zero impact on upstream `nanobot/` core updates.

## **Future Roadmap**
- [ ] **Subagent Queueing:** Mechanism to stack and sequentially execute multiple subagent requests.
- [ ] **Knowledge Graph:** Relationship-based memory beyond basic semantic similarity.
- [ ] **Cross-Device Sync:** Cloud-syncing options for the local ChromaDB database.
- [ ] **Surgical UI:** Slim dashboard for managing "Gold Standard" facts in memory.
