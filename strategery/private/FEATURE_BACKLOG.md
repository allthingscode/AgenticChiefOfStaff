# Strategic Edition: Feature Backlog

This file tracks the high-level status of planned enhancements and new capabilities for Nanobot Strategic Edition. Detailed specifications for each feature are stored in the `./feature_backlog/` folder.

## **Active Features (Planning & Development)**

| ID | Title | Status | Specialist | Description |
|---|---|---|---|---|
| F-001 | **Strategic Knowledge Graph (NanoGraph)** | Phase 1 Done | Architect | Automated extraction of entities and relationships from conversation history into a persistent graph. |
| F-002 | **Context Compaction Protocol** | Research | Researcher | Strategic pruning of old context using LLM-generated "Memory Capsules" to maintain high signal-to-noise. |
| F-003 | **Subagent Health Heartbeat** | Inactive | Researcher | Automated periodic health checks for MCP servers and external API connectivity with status reporting. |
| F-004 | **Subagent Queueing** | Planning | Architect | Mechanism to stack and sequentially execute multiple subagent requests to prevent resource contention. |
| F-005 | **Cross-Device Sync** | Research | Researcher | Explore options for syncing the local ChromaDB database and history across multiple devices. |
| F-006 | **Surgical UI** | Planning | Architect | Minimal dashboard for managing "Gold Standard" facts and inspecting the knowledge graph. |
| F-007 | **Memory Search Tool** | Planning | Researcher | Explicit `search_memory` tool for agents to proactively query the ChromaDB vector store. |
| F-008 | **Rolling Journal Injection** | Research | Researcher | Always inject recent entries from the daily Markdown journals into the prompt for immediate continuity. |
| F-009 | **Hybrid Memory Index** | Research | Architect | Integrate SQLite FTS5 alongside ChromaDB to enable precise keyword matching for IDs and technical terms. |

---
*Updated on 2026-03-04 by nanobot 🐾*
