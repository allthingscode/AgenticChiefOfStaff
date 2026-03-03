# Strategic Edition: Private Bug Backlog

This file tracks technical issues, regressions, and internal bugs with this custom version of nanobot.

## **Active Issues (Open)**

| ID | Title | Priority | Description |
|---|---|---|---|
| BUG-030 | Regression: Vector Store Embedding Provider Loss | Critical | Vector Store singleton loses its embedding provider reference during or after memory consolidation. **Update:** Implemented defensive late-patching and diagnostic logging. |
| BUG-031 | Failure: Tool Stripping & Mandate Bypass (Main Agent) | High | Main Agent continues to attempt restricted tool calls (e.g., `mcp_google-ai-search`) and mandate bypasses via `exec`. |
| BUG-032 | Tool Stripping Initialization Bug | High | Inconsistent tool stripping during startup. **Update:** Added diagnostic telemetry to track registration turns. |
| BUG-033 | Test Infrastructure Failure (Core & Strategic) | Medium | Core and Strategic tests fail to run out-of-the-box due to missing `pythonpath` configuration and `strategery/__init__.py`. Core `test_cron_service.py` is failing due to a race condition. |
| BUG-034 | Telegram Polling Resilience (High) | Defended | Network errors (`httpx.ReadError`) during Telegram polling cause fatal process termination. Fixed via monkey-patch in `TelegramPatch` with exponential backoff. |

---
*Created on 2026-03-01 by nanobot 🐾*
*Updated on 2026-03-03 by nanobot 🐾*
