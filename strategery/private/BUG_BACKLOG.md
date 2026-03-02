# Strategic Edition: Private Bug Backlog

This file tracks technical issues, regressions, and internal bugs with this custom version of nanobot.

## **Verified Fixes (Completed)**

### **[BUG-001] Subagent Model Verification Failure**
- **Status:** FIXED & VERIFIED
- **Progress:** Tool stripping and model routing confirmed working in live logs.

### **[BUG-002] Recurring Local logs/ Directory**
- **Status:** FIXED & VERIFIED
- **Progress:** Strategic logs now consistently redirect to the D: drive upon config load.

### **[BUG-003] Tool Stripping Bypass**
- **Status:** FIXED & VERIFIED
- **Progress:** Main Agent is strictly blocked from executing restricted tools directly.

### **[BUG-004] Strategic Shutdown Timeout**
- **Status:** FIXED & VERIFIED
- **Progress:** Signal handoff logic ensures core shutdown completes after strategic hooks.

### **[BUG-005] Transient Subagent Patch AttributeError**
- **Status:** FIXED & VERIFIED
- **Progress:** Race condition resolved via modular import structure.

### **[BUG-006] Cron Storage Path Drift**
- **Status:** FIXED & VERIFIED
- **Progress:** Cron service correctly loads jobs from the strategic D: drive.

### **[BUG-007] Reasoning Leak & Looping**
- **Status:** FIXED & VERIFIED
- **Progress:** Advanced regex and circuit breaker prevent reasoning leakage.

### **[BUG-008] MCP Tool Name Drift**
- **Status:** FIXED & VERIFIED
- **Progress:** Broad pattern matching catches all surgical tool variations.

### **[BUG-009] Upstream 500 Error Leakage**
- **Status:** FIXED & VERIFIED
- **Progress:** Strategic error interceptor formats technical errors into user-friendly mandates.

### **[BUG-010] Idle Polling Loop (exec)**
- **Status:** FIXED & VERIFIED
- **Progress:** Shell-based polling loops are detected and broken after 3 attempts.

### **[BUG-011] Subagent MCP Isolation**
- **Status:** FIXED & VERIFIED
- **Progress:** Overhauled subagent manager provides native MCP access to specialists.

### **[BUG-012] CLI Tool Bypass via 'exec'**
- **Status:** FIXED & VERIFIED
- **Progress:** Blocks direct calls to `nanobot` CLI from the main agent loop.

### **[BUG-013] Semantic Retrieval AttributeError**
- **Status:** FIXED & VERIFIED
- **Progress:** Resolved `storage_root` access failure in RAG logic.

### **[BUG-014] Subagent Spawn Loop**
- **Status:** FIXED & VERIFIED
- **Progress:** Enforced turn termination after `spawn` and blocked `HISTORY.md` polling.

### **[BUG-015] Intermittent Strategic Embedding API Error**
- **Status:** FIXED & VERIFIED
- **Progress:** Implemented exponential backoff retry logic in `strategic_litellm_embed` wrapper.

---
*Created on 2026-03-01 by nanobot 🐾*
