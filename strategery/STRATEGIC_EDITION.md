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

### **Memory Roadmap (Upcoming)**
- **Hybrid Memory Index:** Layering **SQLite FTS5** over ChromaDB for 100% precision on technical IDs and keywords.
- **Proactive Memory Retrieval:** Transitioning from passive system-injected context to explicit agent-managed `search_memory` tools.
- **Chronological Continuity:** Automated rolling injection of daily journal snapshots for seamless session-to-session awareness.

### **2. "Clean History" Consolidation**
- **Bloat Prevention:** Replaces linear history files with high-density Vector Store summaries.
- **Surgical Ingestion:** Summaries and memory updates are automatically vectorized during consolidation.
- **Daily Journals:** Chronological journals provide human-readable snapshots without context window bloat.

### **3. Advanced Telegram Integration**
- **Topic/Thread Awareness:** Full support for Telegram Topics (sessions map correctly to thread IDs).
- **Redirection Logic:** Automatically redirects all media (photos, voice, documents) to a dedicated local storage directory.

### **4. Specialist Economy & Delegation**
- **Enforced Delegation:** The Main Agent is strictly blocked from executing high-power surgical tools (Google, AI Search, Email).
- **Explicit Specialist Routing:** Orchestrator-driven delegation where the agent chooses between **'researcher'** (default) or **'architect'** types.
- **Model Isolation:** Specialist models are strictly assigned by the system (e.g., `gemini-1.5-pro` for architects, `gemini-1.5-flash` for researchers).
- **Hardened Execution:** Integrated circuit breakers and loop detection prevent amnesia loops or tool abuse by both the Main Agent and Specialists.
- **Orchestrator Reports:** Formatted specialist reports with directive-driven hint injection to ensure the Main Agent only synthesizes subagent work.
- **Enhanced Mandate Enforcement:** Hardened filters and monitoring prevent bypass attempts (e.g., 'exec', 'ping', 'dir', 'python'), ensuring strict adherence to the delegation model.

### **5. Infrastructure & Resilience**
- **Unified CLI Wrapper:** The `strategery\nanobot.cmd` script enforces all strategic patches across ALL commands (e.g., `nanobot status`, `nanobot gateway`).
- **Persistent MCP Connections:** `StrategicMcpManager` maintains persistent server sessions across subagent spawns to eliminate startup latency.
- **Self-Awareness Context:** Tracks environmental changes and architectural updates to keep the agent informed of its own state.
- **BOM Safety:** Global monkey-patch for `builtins.open` ensures all JSON/JSONL files are read correctly on Windows.
- **Resilient Provider Stack:** Universal embedding access across all provider types via base-class patching and robust retry loops with exponential backoff for transient upstream errors.
- **Zero Core Pollution:** 100% of strategic logic is contained in `strategery/patches/`, ensuring zero impact on upstream `nanobot/` core updates.

### **6. Graph Capabilities (NanoGraph)**
- **Semantic Overlay:** The memory system is augmented with a semantic graph overlay for relationship-based recall.
- **Neighbor Querying:** Find related entities for a specific memory node using relationship types.
- **Surgical Tools:** Accessible via `python D:\Nanobot_Storage\workspace\skills\memory\scripts\graph_query.py`.
