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

## **[BUG-021] Main Agent Mandate Bypass Attempts (Behavioral)**
- **Status:** FIXED & VERIFIED
- **Priority:** MEDIUM
- **Progress:** Added system prompt hardening in `ConfigPatch` to wrap `ContextBuilder.build_system_prompt` and inject strict directives against using `exec` for restricted operations (like `nanobot` CLI or polling loops). This reduces "bypass chatter" before the tool-level security filters (BUG-012) even need to engage.
- **Description:** Mitigated issue where the Main Agent was repeatedly attempting to bypass tool restrictions using the `exec` tool.

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

## **[BUG-026] Subagent Connectivity Diagnostic Failure (ping Access Denied)**
- **Status:** FIXED & VERIFIED
- **Priority:** MEDIUM
- **Progress:** Patched `SubagentManager._build_subagent_prompt` in `SubagentPatch` to explicitly warn specialists against using `ping` via `exec` on Windows due to OS restrictions.
- **Description:** Specialists were reporting false network failures after their `ping` commands were blocked by the OS.

## **[BUG-027] Subagent Search Tool Misconfiguration (Google AI Search)**
- **Status:** FIXED & VERIFIED
- **Priority:** HIGH
- **Progress:** Removed the deprecated `WebSearchTool` from the specialist subagent's `ToolRegistry` and patched `SubagentManager._build_subagent_prompt` to provide explicit instructions for using the `mcp_google-ai-search_search_ai` tool.
- **Description:** Specialists reported missing or misconfigured search tools because they were attempting to use the deprecated/unconfigured `web_search` instead of the mandated MCP tool.

## **[BUG-024] Memory Flush Mandate Bypass (Main Agent tries manual log writes)**
- **Status:** FIXED & VERIFIED
- **Priority:** HIGH
- **Progress:** Hardened the global system prompt mandate in `ConfigPatch` to explicitly forbid manual management of `history.md` or log files. Reinforced this with specific instructions in `MemoryPatch` during flush turns.
- **Description:** Main Agent was attempting to bypass automated consolidation by manually writing history to disk.

## **[BUG-025] Gemini 503 (ServiceUnavailableError) on Subagent Requests**
- **Status:** FIXED & VERIFIED
- **Priority:** LOW
- **Progress:** Addressed by the hardened retry logic in `ProviderPatch` which now handles 503 errors with exponential backoff for all requests (Main and Subagent).
- **Description:** Transient 503 errors were causing subagent failures.

## **[BUG-028] Main Agent restricted tool violation (`mcp_google-ai-search`)**
- **Status:** FIXED & VERIFIED
- **Priority:** HIGH
- **Progress:** Updated global system prompt mandates in `ConfigPatch` to explicitly name specialist tools and forbid direct calls, reinforcing the `spawn` delegation model.
- **Description:** Main Agent was attempting to call research tools directly instead of spawning a specialist.

## **[BUG-029] Strategic Retry Failure on Upstream 500 Error**
- **Status:** FIXED & VERIFIED
- **Priority:** CRITICAL
- **Progress:** Implemented a robust 3-attempt retry loop with exponential backoff in `ProviderPatch`. Added logic to distinguish between transient (500, 503, 429) and permanent (400, 401, 403) errors to avoid redundant calls on hard blocks.
- **Description:** User reported session block due to 500 error not being successfully retried.

## **[BUG-030] Vector Store Embedding Provider Loss**
- **Status:** FIXED & VERIFIED
- **Priority:** CRITICAL
- **Progress:** Implemented defensive "Late-Patching" in `VectorStoreFactory` to force-attach the `embed` method to the provider if lost during consolidation. Added diagnostic telemetry to track provider state.
- **Description:** Vector Store singleton would occasionally lose its embedding provider reference, causing consolidation failures.

## **[BUG-034] Telegram Polling Resilience**
- **Status:** FIXED & VERIFIED
- **Priority:** HIGH
- **Progress:** Implemented an exponential backoff retry loop (5s to 60s) in `TelegramPatch` to catch `NetworkError` and `ReadError` during polling.
- **Description:** Transient network errors were causing the entire Nanobot process to terminate.

## **[BUG-035] Memory Path Discrepancy**
- **Status:** FIXED & VERIFIED
- **Priority:** HIGH
- **Progress:** Updated `SUITE.md` and `SubagentPatch` to correctly point to `D:\Nanobot_Storage\workspace\memory` instead of legacy paths.
- **Description:** Subagents/Health Checks were failing due to looking for memory in the wrong location on the D: drive.

## **[BUG-036] Retired File Dependency (HISTORY.md)**
- **Status:** DEFENDED & VERIFIED
- **Priority:** MEDIUM
- **Progress:** Updated `SubagentPatch` specialist instructions to explicitly mandate the retirement of `HISTORY.md` and the use of the new Vector Store/Journal system.
- **Description:** Subagents were still attempting to use the retired `HISTORY.md` file for memory operations.

---
*Archived on 2026-03-03 by nanobot 🐾*

## **[BUG-037] Health Suite Syntax Error (SUITE.md)**
- **Status:** FIXED & VERIFIED
- **Priority:** HIGH
- **Progress:** Fixed SyntaxError in `SUITE.md` by moving comments outside of backticks in the pytest command. Also fixed AsyncExitStack shutdown hook in `infra.py` and improved `nanobot.cmd` path resolution.
- **Description:** Automated health suite was failing due to improper command formatting and cleanup errors.


## **[BUG-033] Core Test Race Condition (test_cron_service.py)**
- **Status:** FIXED & VERIFIED
- **Priority:** MEDIUM
- **Progress:** Implemented `CronPatch` to enhance `jobs.json` reload detection using file-size monitoring.
- **Description:** Fixed flaky core tests on Windows where low mtime resolution caused missed reload triggers.

## **[BUG-042] Subagent Startup Regression (SyntaxError)**
- **Status:** FIXED & VERIFIED
- **Priority:** HIGH
- **Progress:** Fixed a SyntaxError in `SubagentPatch` introduced during security hardening of the `ToolRegistry.execute` patch.
- **Description:** Subagent system was failing to initialize due to a malformed `if` statement in the `exec` bypass filter.

## **[BUG-043] Subagent Iteration Timeout (System Health)**
- **Status:** FIXED & VERIFIED
- **Priority:** HIGH
- **Progress:** Hardened `SubagentPatch` with specialist loop detection (limit 5) and blocked empty tool-call responses. Enhanced iteration logging for visibility.
- **Description:** Researcher specialist was hitting the 15-iteration limit instantly due to a tight tool-call loop in the health suite.

## **[BUG-044] Subagent: False Timeout (Empty LLM Response)**
- **Status:** FIXED & VERIFIED
- **Priority:** CRITICAL
- **Progress:** Patched `SubagentPatch` to correctly identify empty LLM responses (e.g., 503s or malformed thoughts) and report them as early exits, rather than erroneously triggering the 15-iteration timeout fallback.
- **Description:** Subagent reported a timeout after 15 iterations even when breaking the loop early due to an empty response.

## **[BUG-046] Orchestrator: Redundant Directive Injection**
- **Status:** FIXED & VERIFIED
- **Priority:** LOW
- **Progress:** Removed redundant orchestrator hint injection from `MemoryPatch` since it's already handled cleanly in `SubagentPatch._announce_result`.
- **Description:** Subagent reports in session history were bloated with three separate sets of overlapping instructions.

## **[BUG-045] Subagent: Sequential MCP Connection Latency**
- **Status:** FIXED & VERIFIED
- **Priority:** MEDIUM
- **Progress:** Parallelized MCP server initialization in `StrategicMcpManager` using `asyncio.gather`. Added `_ensure_connection` helper with fine-grained locking to allow concurrent startup of different servers.
- **Description:** Subagent startup was delayed by 10-15s because MCP servers were connecting one-by-one.

---
*Archived on 2026-03-04 by nanobot 🐾*


