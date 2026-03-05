# Strategic Edition: Private Bug Backlog

This file tracks technical issues, regressions, and internal bugs with this custom version of nanobot.

## **Active Issues (Open)**

| ID | Title | Priority | Description |
|---|---|---|---|
| BUG-031 | Monitoring: Tool Stripping & Mandate Bypass | High | Main Agent mandate bypasses (via `exec`) are currently blocked by filters, but we are monitoring for new creative attempts (e.g. `type`, `cat`, `Get-Content`). |
| BUG-032 | Monitoring: Tool Stripping Initialization | High | Monitoring the `ToolRegistry` via diagnostic telemetry to ensure restricted tools are stripped across all session startup scenarios. |
| BUG-038 | Google AI Search: Shallow Results | Medium | `search_ai` returning 0 citations/sources on valid queries. Fragility due to hard-coded selectors in `google-ai-mode-mcp` (npm package). |
| BUG-045 | Subagent: Sequential MCP Connection Latency | Medium | MCP server connections during subagent startup occur sequentially, adding significant latency (10s+) before the first iteration. |
| BUG-047 | Subagent: Behavioral Amnesia (False Success) | Critical | Specialist subagents are reporting "success" after reading instructions but without actually calling the required verification tools. |
| BUG-048 | Researcher: Prompt Drowning (Context Bloat) | High | The `researcher` specialist (Flash Lite) is likely being overwhelmed by the injected strategic mandates + the full test suite instructions, leading to early termination. |

## **Completed / Resolved**

| ID | Title | Resolution |
|---|---|---|
| BUG-043 | Subagent: Iteration Timeout (System Health) | Fixed by implementing specialist loop detection (limit 5) and hardening the subagent loop against empty tool-call responses. Enhanced iteration logging. |
| BUG-040 | Subagent: False Success on LLM Failure | Fixed error propagation in `SubagentPatch`. Fatal LLM errors (503) and timeouts are now correctly reported as failures. |
| BUG-041 | Subagent: Workspace Root Confusion | Fixed by forcing `D:\Nanobot_Storage` workspace root in `SubagentPatch` for all subagent tool initializations. |
| BUG-039 | Subagent Task Truncation (Logging) | Increased `display_label` length from 30 to 100 characters in `_patched_spawn`. |

---
*Created on 2026-03-01 by nanobot 🐾*
*Updated on 2026-03-04 by nanobot 🐾*
