# Strategic Edition: Feature Backlog

This file tracks the high-level status of planned enhancements and new capabilities for Nanobot Strategic Edition. Detailed specifications for each feature are stored in the `./feature_backlog/` folder.

## **Active Features (Ordered by Strategic Priority)**

| ID | Title | Priority | Status | Success Criteria | Strategic Risk |
|---|---|---|---|---|---|
| F-002 | **Context Compaction** | **HIGH** | Planning | 30% reduction in long-session tokens. | Medium: Memory loss if logic is too aggressive. |
| ARCH-022 | **Multimodal Subagent Support** | **HIGH** | In-Flight | Specialists can analyze 100% of passed images. | High: Vision tools must be isolated from core. |
| F-031 | **Generator-Evaluator Loop** | **MEDIUM** | Planning | 50% reduction in hallucinated tool calls. | Medium: Turn-count increases (cost). |
| F-040 | **Git MCP Server** | **HIGH** | **GLOBAL** | 100% reliability in PRs/Commits; 0 ParserErrors. | Low: Industry-standard MCP integration. |
| F-041 | **Role-Based Templates** | **DONE** | [F-041](./feature_backlog/F-041_Role_Based_Templates.md) | strategery/logic/subagent_logic.py |
| F-042 | **Fast-Path Command Suite** | **MEDIUM** | **PROJECT-SPECIFIC** | 50% reduction in turns for common audits. | Low: CLI Command wrappers. |
| F-043 | **Model Tier Evaluation Tool** | **HIGH** | Planning | Periodic audit/suggestion report for tiered cost optimization. | Low: Manual maintenance utility. |

## **Completed or In-Flight (Strategic Patches)**

| ID | Title | Status | Feature File | Core Component |
|---|---|---|---|---|
| ARCH-024 | **State Checkpointing** | **DONE** | [ARCH-024](./feature_backlog/ARCH-024_State_Checkpointing.md) | `strategery/patches/checkpoint.py` |
| F-039 | **Doctor Auto-Heal Mode** | **DONE** | [F-039](./feature_backlog/F-039_Doctor_Auto_Heal.md) | `strategery/strategic_doctor.py` |
| F-038 | **Session Retrospective (SOP-008)** | **DONE** | [F-038](./feature_backlog/F-038_Session_Retrospective_Skill.md) | **Global Skill:** `session-retro` |
| SOP-009 | **Efficiency Acceleration** | **DONE** | - | `ripgrep`, `fd`, `jq` (Scoop tools) |
| F-014 | **High-Readability HTML Reports** | **DONE** | [F-014](./feature_backlog/F-014_High_Readability_HTML_Reports.md) | `strategery/strategic_email_reporter.py` |
| F-028 | **Subagent Logic Simplification** | **DONE** | [F-028](./feature_backlog/F-028_Subagent_Logic_Simplification.md) | `strategery/logic/subagent_logic.py` |
| F-029 | **Subagent Patch Refactoring** | **DONE** | [F-029](./feature_backlog/F-029_Subagent_Patch_Consolidation.md) | `strategery/patches/subagent.py` |
| F-015 | **The Thin Patch Mandate** | **DONE** | [F-015](./feature_backlog/F-015_Logic_vs_Bridge_Separation.md) | `strategery/logic/` & `strategery/patches/` |
| F-016 | **High-Fidelity Telemetry** | **DONE** | - | Real-time visibility into thoughts, args, and result snippets. |
| F-009 | **Hybrid Memory Index** | **DONE** | [F-009](./feature_backlog/F-009_Hybrid_Memory_Index.md) | `strategery/patches/hybrid_store.py` (FTS5 + Chroma) |
| F-007 | **Memory Search Tool** | **DONE** | [F-007](./feature_backlog/F-007_Memory_Search_Tool.md) | `strategery/tools/strategic_memory.py` |
| F-008 | **Rolling Journal Injection** | **DONE** | [F-008](./feature_backlog/F-008_Rolling_Journal_Injection.md) | `strategery/patches/memory.py` |

## **Archived / Scrapped (High Risk / Low Value)**

| ID | Title | Reason for Archiving |
|---|---|---|
| F-004 | **Subagent Queueing** | Superseded by recent high-performance concurrency patches (F-012/F-013). |
| F-005 | **Cross-Device Sync** | Extremely high risk of database corruption (ChromaDB/SQLite) when attempting naive file synchronization. |

---
*Updated on 2026-03-11 by nanobot ðŸ¾*
