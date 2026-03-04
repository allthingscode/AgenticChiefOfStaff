# Strategic Edition: Private Bug Backlog

This file tracks technical issues, regressions, and internal bugs with this custom version of nanobot.

## **Active Issues (Open)**

| ID | Title | Priority | Description |
|---|---|---|---|
| BUG-031 | Monitoring: Tool Stripping & Mandate Bypass | High | Main Agent mandate bypasses (via `exec`) are currently blocked by filters, but we are monitoring for new creative attempts (e.g. `type`, `cat`, `Get-Content`). |
| BUG-032 | Monitoring: Tool Stripping Initialization | High | Monitoring the `ToolRegistry` via diagnostic telemetry to ensure restricted tools are stripped across all session startup scenarios. |
| BUG-038 | Google AI Search: Shallow Results | Medium | `search_ai` returning 0 citations/sources on valid queries. Possible parsing regression. |
| BUG-039 | Subagent Task Truncation (Logging) | Low | `spawn` tool call logs are truncating task descriptions, making auditing difficult. |

---
*Created on 2026-03-01 by nanobot 🐾*
*Updated on 2026-03-03 by nanobot 🐾*
