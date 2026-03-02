# Strategic Edition: Private Bug Backlog

This file tracks technical issues, regressions, and internal bugs with this custom version of nanobot.

## **Critical Backlog**

### **[BUG-001] Subagent Model Verification Failure**
- **Status:** FIXED & VERIFIED
- **Priority:** HIGH
- **Progress:** 
    - **Tool Stripping:** High-power tools (Google, AI Search, Email) are now actively purged/blocked from the Main Agent's registry in `SubagentPatch`.
    - **Forced Delegation:** Main Agent is now forced to call `spawn` to access these tools.
    - **Routing Verified:** Logs confirm `gemini-3-pro-preview` and `gemini-2.5-flash-lite` are correctly assigned during subagent execution.
    - **RAG Hardening:** Added "MAY BE STALE" warning to RAG context to prevent memory short-circuiting.
    - **Automated Testing:** Implemented comprehensive unit tests in `strategery/tests/unit/test_specialist_routing.py` (100% pass).
- **Goal:** Ensure subagents use their assigned models (e.g., `gemini-1.5-pro` for researchers) even when memory hits exist.
- **Related Files:** `strategery/patches/subagent.py`, `strategery/tests/unit/test_specialist_routing.py`.

### **[BUG-002] Recurring Local logs/ Directory**
- **Status:** FIXED & VERIFIED
- **Priority:** MEDIUM
- **Progress:** 
    - **Dynamic Redirection:** `strategic_logger.py` now supports re-initialization with a specific directory.
    - **Late Initialization:** `strategery/patches/__init__.py` re-configures the logger to point to `STORAGE_ROOT/logs` immediately after the config is loaded.
    - **Verification:** `strategic.log` is now correctly written to the D: drive.
- **Goal:** Identify the specific import or initialization step triggering the default path and suppress it.
- **Related Files:** `strategery/strategic_logger.py`, `strategery/patches/__init__.py`.

### **[BUG-003] Tool Stripping Bypass**
- **Status:** FIXED & VERIFIED
- **Priority:** CRITICAL
- **Progress:** 
    - **Persistent Gatekeeper:** `ToolRegistry.register` and `ToolRegistry.execute` are now patched to act as permanent gatekeepers.
    - **Hard Block:** Any attempt by the Main Agent to execute a tool matching `BLOCKED_PATTERNS` is immediately rejected with a mandate-based error.
    - **Circuit Breaker:** Repeated attempts (>=2) trigger a `HARD-LOCK` error to prevent idle token-burning loops.
- **Goal:** Completely prevent the Main Agent from ever seeing or executing high-power surgical tools.
- **Related Files:** `strategery/patches/subagent.py`, `strategery/tests/unit/test_subagent_late_blocking.py`.

### **[BUG-004] Strategic Shutdown Timeout**
- **Status:** FIXED & VERIFIED
- **Priority:** HIGH
- **Progress:** 
    - **Signal Capture Task:** `LifecycleManager` now runs a background task to capture core Nanobot signal handlers set after startup.
    - **Handoff Mechanism:** Strategic hooks run first, then original handlers are restored and signals are re-sent (via `os.kill`) to trigger core cleanup.
    - **Safety Extension:** Shutdown timeout increased to 10 seconds to allow core services (MCP, Channels) to finish.
- **Goal:** Ensure both strategic and core shutdown sequences execute fully.
- **Related Files:** `strategery/patches/lifecycle.py`.

### **[BUG-005] Transient Subagent Patch AttributeError**
- **Status:** FIXED & VERIFIED
- **Priority:** LOW
- **Description:** Logs show a one-time error: `'SubagentPatch' object has no attribute '_patch_subagent_manager'` at `20:03:36`.
- **Status:** Resolved. The error was a transient side-effect of an incomplete `replace` operation during an earlier session. Subsequent runs show clean initialization of the subagent manager patch.
- **Related Files:** `strategery/patches/subagent.py`, `strategery/patches/__init__.py`.

### **[BUG-006] Cron Storage Path Drift**
- **Status:** FIXED & VERIFIED
- **Priority:** HIGH
- **Progress:** 
    - **Data Dir Redirection:** `ConfigPatch` now successfully overrides `nanobot.config.loader.get_data_dir` to point to `STORAGE_ROOT` (D: drive).
    - **Verification:** Logs confirm `CronService` correctly identifies and loads 3 jobs from the D: drive, while the local `~/.nanobot` store remains empty.
- **Goal:** Force the `CronService` to use the strategic storage path for all jobs.
- **Related Files:** `strategery/patches/config.py`.

### **[BUG-007] Reasoning Leak & Looping ("thought" in output)**
- **Status:** FIXED & VERIFIED
- **Priority:** CRITICAL
- **Progress:** 
    - **Enhanced Regex:** `ProviderPatch._patched_strip_think` now aggressively strips `Thought:`, `Reasoning:`, and markdown-style variants (`**Thought:**`) across multiple lines.
    - **Case Insensitivity:** All patterns are now case-insensitive.
    - **Circuit Breaker:** If a response is 100% reasoning, a strategic placeholder is injected to prevent the agent from looping or presenting an empty response.
    - **Automated Testing:** Verified with 6 comprehensive test cases in `strategery/tests/unit/test_provider_patch.py`.
- **Goal:** Completely suppress all reasoning artifacts from user-facing channels and prevent idle loops.
- **Related Files:** `strategery/patches/provider.py`, `strategery/tests/unit/test_provider_patch.py`.

### **[BUG-008] MCP Tool Name Drift / Blocking Failure**
- **Status:** FIXED & VERIFIED
- **Priority:** HIGH
- **Progress:**
    - **Broader Matching:** `SubagentPatch` now uses a case-insensitive `BLOCKED_PATTERNS` list including "google", "ai-search", "email-reporter", and "web_search".
    - **Late Registration Handling:** Patched `ToolRegistry.register` now filters tools in real-time as they are added (e.g. via lazy MCP connections).
    - **Deprecation Hints:** Added specific contextual hints for `web_search` to guide the agent toward `mcp_google-ai-search_search_ai`.
- **Goal:** Ensure the "Hard Block" in `ToolRegistry.execute` is robust against all high-power tool variations.
- **Related Files:** `strategery/patches/subagent.py`, `strategery/tests/unit/test_subagent_late_blocking.py`.

### **[BUG-009] Upstream 500 Error Leakage**
- **Status:** FIXED & VERIFIED
- **Priority:** HIGH
- **Progress:** 
    - **Strategic Error Interceptor:** `ProviderPatch._patched_chat` now intercepts `finish_reason="error"` responses.
    - **Graceful Formatting:** Raw technical JSON/LiteLLM exceptions are converted into user-friendly messages prefixed with `[STRATEGIC]`.
    - **Retry Logic:** Implemented a one-time automatic retry (1.5s delay) for transient errors like `InternalServerError (500)` and `ServiceUnavailable (503)`.
    - **Automated Testing:** Verified with 7 test cases in `strategery/tests/unit/test_provider_patch.py`.
- **Goal:** Intercept upstream errors and present a graceful "Strategic" notification or implement a retry/fallback mechanism.
- **Related Files:** `strategery/patches/provider.py`, `strategery/tests/unit/test_provider_patch.py`.

### **[BUG-010] Idle Polling Loop (exec polling)**
- **Status:** FIXED & VERIFIED
- **Priority:** HIGH
- **Progress:**
    - **Polling Detection:** `SubagentPatch` now tracks `exec` command history for the Main Agent.
    - **Hard Block:** Repeated status/ping polling (>=3 times) is blocked with a mandate to synthesize existing information.
    - **Aggressive Directive:** Improved the Specialist Subagent Report to include a high-priority "TERMINATE TURN" directive.
- **Goal:** Prevent the Main Agent from burning tokens in tight `status` polling loops.
- **Related Files:** `strategery/patches/subagent.py`, `strategery/tests/unit/test_loop_prevention.py`.

### **[BUG-011] Subagent MCP Isolation**
- **Status:** FIXED & VERIFIED
- **Priority:** HIGH
- **Progress:**
    - **MCP Injection:** `SubagentManager._run_subagent` has been overhauled to correctly initialize and connect MCP servers for each subagent session.
    - **Specialist Economy:** Subagents now have full, native access to `mcp_google-surgical_`, `mcp_google-ai-search_`, and `mcp_email-reporter_`.
- **Goal:** Grant subagents the surgical tools they need to be effective specialists.
- **Related Files:** `strategery/patches/subagent.py`.

### **[BUG-012] CLI Tool Bypass via 'exec'**
- **Status:** FIXED & VERIFIED
- **Priority:** CRITICAL
- **Progress:**
    - **Bypass Detection:** `SubagentPatch._patched_tool_execute` now inspects `exec` commands for patterns like `python -m nanobot mcp ...`.
    - **Immediate Block:** Any attempt to call restricted tools via the CLI is blocked with a "Strategic Mandate Violation" error.
    - **Automated Testing:** Verified with 3 new test cases in `strategery/tests/unit/test_loop_prevention.py`.
- **Goal:** Close the loophole where the agent uses the shell to bypass tool blocking.
- **Related Files:** `strategery/patches/subagent.py`, `strategery/tests/unit/test_loop_prevention.py`.

### **[BUG-013] Semantic Retrieval AttributeError**
- **Status:** FIXED & VERIFIED
- **Priority:** HIGH
- **Progress:**
    - **Context Loading:** `MemoryPatch` and `VectorStoreFactory` now derive `storage_root` via `load_strategic_context()` instead of unreliable package imports.
- **Goal:** Ensure RAG context injection works without crashing on D: drive redirection.
- **Related Files:** `strategery/patches/memory.py`, `strategery/patches/vsa.py`.

### **[BUG-014] Subagent Spawn Loop (HISTORY.md Polling)**
- **Status:** FIXED & VERIFIED
- **Priority:** CRITICAL
- **Progress:**
    - **Turn Enforcement:** The `spawn` tool now returns an explicit `STOP Turn` mandate to the Main Agent, instructing it to end its response immediately.
    - **History Bypass Block:** `exec` now explicitly blocks attempts to read or `findstr` the retired `HISTORY.md` file.
    - **Loop Breaker Hardening:** Polling detection now catches `findstr` and `grep` patterns associated with file-based polling.
- **Goal:** Prevent the Main Agent from polling for subagent results via retired file mechanisms.
- **Related Files:** `strategery/patches/subagent.py`, `strategery/tests/unit/test_loop_prevention.py`.

## **Future Enhancements**
- [ ] **Subagent Request Queueing:** Mechanism to stack and sequentially execute multiple subagent requests to prevent system overwhelm.

---
*Created on 2026-03-01 by nanobot 🐾*
