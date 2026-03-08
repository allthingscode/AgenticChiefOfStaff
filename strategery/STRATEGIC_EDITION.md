# Nanobot Strategic Edition

## **Overview**
The Strategic Edition is a modular, high-performance extension of the Nanobot Core, specifically designed for deep integration with senior-level productivity workflows. It focuses on **Zero Core Pollution**, **Hybrid Memory**, and **Surgical Tooling**.

## **Key Features & Differences**

### **1. Hybrid Memory Architecture (RAG)**
- **Hybrid Index:** Combines **SQLite FTS5 (Keyword)** and **ChromaDB (Vector)** for 100% precision on technical IDs and high-recall semantic search.
- **Active RAG (search_memory):** Specialist subagents have explicit access to a `search_memory` tool for proactive, deep-dive context retrieval.
- **Chronological Continuity:** Automated **Rolling Journal** injection provides seamless session-to-session awareness from daily journal snapshots.
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

### **4. Specialist Economy & Delegation**
- **Enforced Delegation:** The Main Agent is strictly blocked from executing high-power surgical tools (Google, AI Search, Email).
- **Explicit Specialist Routing:** Orchestrator-driven delegation where the agent chooses between **'researcher'** (default) or **'architect'** types.
- **Model Isolation:** Specialist models are strictly assigned by the system (e.g., `gemini-3-flash-preview` for researchers, `gemini-3-pro-preview` for architects).
- **Hardened Execution:** Integrated circuit breakers and loop detection prevent amnesia loops or tool abuse by both the Main Agent and Specialists.
- **Orchestrator Reports:** Formatted specialist reports with directive-driven hint injection to ensure the Main Agent only synthesizes subagent work.
- **Enhanced Mandate Enforcement:** Hardened filters and monitoring prevent bypass attempts (e.g., 'exec', 'ping', 'dir', 'python'), ensuring strict adherence to the delegation model.   

### **5. Infrastructure & Resilience**
- **Unified CLI Wrapper:** The `strategery\nanobot.cmd` script enforces all strategic patches across ALL commands (e.g., `nanobot status`, `nanobot gateway`).
- **Specialist Subagent Persistence:** Utilizes host-bridged MCP sessions to enable near-instant subagent spawning and reuse of active server processes.
- **Strategic Noise Suppression:** Automated suppression of transient network tracebacks (e.g. Telegram RemoteProtocolError) into single-line warnings for cleaner strategic logging.
- **Self-Awareness Context:** Tracks environmental changes and architectural updates to keep the agent informed of its own state.
- **BOM Safety:** Global monkey-patch for `builtins.open` ensures all JSON/JSONL files are read correctly on Windows.
- **Resilient Provider Stack:** Universal embedding access across all provider types via base-class patching and robust retry loops with exponential backoff for transient upstream errors. Now includes direct **Azure OpenAI Provider** support (API 2024-10-21) with strategic logging and formatted error interception.
- **Logging Stability:** Specialized `UnicodeSafeStreamHandler` prevents application crashes when logging complex characters (emojis) to restricted Windows consoles.
- **Notification Resilience:** The Email Reporter includes an automated disk-based fallback (`NOTIFICATIONS.md`) to prevent data loss during API outages or credential revocations.
- **Zero Core Pollution:** 100% of strategic logic is contained in `strategery/patches/`, ensuring zero impact on upstream `nanobot/` core updates and enabling seamless synchronization with the main repository.
- **Upstream Resilience:** Proactive maintenance and architectural alignment of strategic patches with core utility evolutions to ensure long-term stability and compatibility with upstream refactoring.

### **6. Automated Batch System (F-011)**
- **Modular Task Loader:** Folder-based nightly processing where new tasks (maintenance, reporting, extraction) are defined as simple Markdown files in `D:/Nanobot_Storage/workspace/cron/items/`.
- **Specialist Orchestration:** Automated tasks leverage the Specialist Economy, spawning targeted subagents (Researcher/Architect) to perform deep-dive work.
- **Routable Delivery:** Integrated channel redirection ensuring batch reports are delivered to the most recent active user channel (e.g., Telegram) instead of the local CLI.
- **Self-Correcting Schedules:** Strategic Cron patch monitors file state to automatically reload schedules without system restarts or configuration surgery.


### **8. High-Performance Concurrency (F-012, F-013)**
- **Concurrent Agent Loop (Per-Session Lock):** Replaces the global agent lock with a high-performance WeakValueDictionary of per-session locks. This allows the Strategic Edition to process messages from multiple users (e.g., separate Telegram users, CLI sessions, and Cron tasks) simultaneously while ensuring message ordering is strictly preserved for each individual user.
- **Asynchronous Session Persistence:** Patched the session saving logic to use non-blocking asynchronous disk I/O (offloaded to a thread pool). This prevents large conversation histories or complex session metadata from blocking the main event loop, ensuring the system remains responsive even under heavy concurrent load.
### **7. Graph Capabilities (NanoGraph)**
- **Semantic Overlay:** The memory system is augmented with a semantic graph overlay for relationship-based recall.
- **Neighbor Querying:** Find related entities for a specific memory node using relationship types.
- **Surgical Tools:** Accessible via `python D:\Nanobot_Storage\workspace\skills\memory\scripts\graph_query.py`.
