# Strategic Edition: Completed Bug Log

This file archives technical issues and regressions that have been resolved and verified.

## **[BUG-001] Subagent Model Verification Failure**
- **Status:** FIXED & VERIFIED
- **Progress:** Patched `SubagentManager._run_subagent` to correctly map specialist models from `config.json`.

## **[BUG-002] Workspace Path Injection (Windows)**
- **Status:** FIXED & VERIFIED
- **Progress:** Added absolute path resolution and environment normalization for `D:\Nanobot_Storage`.

## **[BUG-003] Tool Stripping Bypass**
- **Status:** FIXED & VERIFIED
- **Progress:** Implemented `ToolRegistry.register` monkey-patch in `SubagentPatch`.

## **[BUG-004] BOM Validation Error on config.json**
- **Status:** FIXED & VERIFIED
- **Progress:** Enforced `utf-8-sig` for all `.json` file reads in `config.py` and patched global `open`.

## **[BUG-005] Subagent Lifecycle Management (Windows)**
- **Status:** FIXED & VERIFIED
- **Progress:** Integrated `lifecycle_manager` with `AgentLoop` and `SubagentManager` for clean session teardown.

## **[BUG-006] Vector Store Retrieval Collision**
- **Status:** FIXED & VERIFIED
- **Progress:** Updated `StrategicVectorStore` to use per-session collection names and namespace isolation.

## **[BUG-007] Reasoning Leak & Looping**
- **Status:** FIXED & VERIFIED
- **Progress:** Implemented `AgentLoop._strip_think` patch and added a "Reasoning Stripper" circuit breaker.

## **[BUG-008] Subagent MCP Connection Leak**
- **Status:** FIXED & VERIFIED
- **Progress:** Wrapped subagent MCP connections in an `AsyncExitStack` for guaranteed cleanup.

## **[BUG-009] Orchestrator System Hint Injection**
- **Status:** FIXED & VERIFIED
- **Progress:** Patched `AgentLoop._process_message` to append turn-termination directives to subagent results.

## **[BUG-010] Idle Polling Loop (exec)**
- **Status:** FIXED & VERIFIED
- **Progress:** Implemented `exec` command history in `ToolRegistry` with loop detection circuit breaker.

## **[BUG-011] RAG Junk Filter Regression**
- **Status:** FIXED & VERIFIED
- **Progress:** Added filtering for 'No summary available' and generic 'yes/no' messages in `MemoryPatch`.

## **[BUG-012] CLI Tool Bypass via 'exec'**
- **Status:** FIXED & VERIFIED
- **Progress:** Added a security filter in `ToolRegistry._patched_tool_execute` to block `nanobot` CLI calls via `exec`.

## **[BUG-013] Context 'Amnesia' on Generic Responses**
- **Status:** FIXED & VERIFIED
- **Progress:** Added `is_generic` filter to `MemoryPatch` to prevent RAG injection from drowning out single-word user turns.

## **[BUG-014] Memory Root Drift**
- **Status:** FIXED & VERIFIED
- **Progress:** Patched `VectorStoreFactory.get_store()` to always load `strategic_edition.storage_root` from config instead of deriving it at runtime.

## **[BUG-015] Intermittent Strategic Embedding API Error**
- **Status:** FIXED & VERIFIED (INCOMPLETE)
- **Progress:** Implemented exponential backoff retry logic in `strategic_litellm_embed` wrapper.
- **Note:** Superseded by [BUG-016].

## **[BUG-016] Strategic Embedding Retry Circuit Breaker (Regression)**
- **Status:** FIXED & VERIFIED
- **Progress:** Moved `genai.Client` constructor inside the retry loop and switched to `client.aio.models.embed_content` for true async support. Verified with updated unit tests.

## **[BUG-017] Missing Bootstrap: STRATEGIC_MANDATES.md**
- **Status:** FIXED & VERIFIED
- **Progress:** Created a comprehensive `STRATEGIC_MANDATES.md` file in the `D:/Nanobot_Storage/workspace/` directory to match the `ContextBuilder` expectations.

## **[BUG-018] Memory Root Drift in Test Logs**
- **Status:** FIXED & VERIFIED
- **Progress:** Refactored `strategic_logger.py` to support dynamic re-initialization and re-evaluated `STRATEGIC_LOG_DIR` on setup. Added `get_logger()` helper and updated `PatchRegistry` to re-configure logging at the start of patch application. Verified 100% test segregation (no pollution in `logs/strategic.log`).

## **[BUG-019] Vector Store: No embedding provider available**
- **Status:** FIXED & VERIFIED
- **Priority:** CRITICAL
- **Progress:** Patched `LiteLLMProvider` in `ProviderPatch` to include the `embed` method and default `embedding_model` attribute.
- **Description:** Fixed regression where the embedding method was defined but never attached to the provider class.

## **[BUG-020] Persistent Strategic Embedding API Error**
- **Status:** FIXED & VERIFIED
- **Priority:** HIGH
- **Progress:** Increased `max_retries` to 5 and initial `retry_delay` to 2.0s in `strategic_litellm_embed`.
- **Description:** Improved resilience against transient Google Embedding API errors by using more conservative retry parameters.

## **[BUG-022] Self-Correction Diagnostic Loop (Recursion)**
- **Status:** RESOLVED
- **Priority:** HIGH
- **Progress:** Identified as a cascading failure from [BUG-019]. The trigger for the loop (Vector Store failure) has been eliminated.
- **Description:** Fixed the underlying embedding issue that caused the agent to spawn redundant diagnostic subagents during memory flushes.

## **[BUG-023] Recursive Strategic Re-Initialization (Ghost Restart)**
- **Status:** FIXED & VERIFIED
- **Priority:** HIGH
- **Progress:** Implemented an idempotency guard using a `sys` module flag (`_STRATEGIC_INITIALIZED`) in `strategery/patches/__init__.py`. Verified that multiple imports/reloads no longer trigger redundant patch applications. Added PID logging to the strategic logger for process boundary auditing.
- **Description:** Fixed issue where subagent spawning or config reloads triggered the entire strategic initialization sequence multiple times within the same process.

---
*Archived on 2026-03-02 by nanobot 🐾*
