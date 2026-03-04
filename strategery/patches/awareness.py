import os
from datetime import datetime
from pathlib import Path
from . import BasePatch
from strategery.strategic_logger import strategic_logger

class AwarenessPatch(BasePatch):
    """
    Handles environmental awareness:
    - Generates AWARENESS.md at startup.
    - Injects STRATEGIC_MANDATES.md and AWARENESS.md into core bootstrap.
    """
    
    @property
    def name(self) -> str:
        return "Identity & Awareness"

    def apply(self, config_data: dict) -> bool:
        try:
            from . import STORAGE_ROOT
            self._generate_awareness_file(STORAGE_ROOT)
            self._patch_context_builder()
            return True
        except Exception as e:
            strategic_logger.error(f"Awareness patch error: {e}")
            return False

    def _generate_awareness_file(self, storage_root):
        """Generates a dynamic AWARENESS.md file with current environment details."""
        awareness_path = storage_root / "workspace" / "AWARENESS.md"
        awareness_path.parent.mkdir(parents=True, exist_ok=True)
        
        now = datetime.now().strftime("%A, %B %d, %Y %H:%M:%S")
        content = f"""# 🦅 STRATEGIC AWARENESS & MANDATES
- **Current Time:** {now}
- **Workspace Root:** {storage_root}
- **System Role:** Strategic Orchestrator (Orchestrate & Delegate)
- **Active Drive:** D:/ (High-Capacity Storage)
- **Edition:** Nanobot Strategic Edition (Zero Core Pollution)

## ⚖️ THE SPECIALIST ECONOMY (ENFORCED)
- **Direct Execution Blocked:** You (the Main Agent) are **PROHIBITED** from running surgical or research tools (Google/Web/Email) directly.
- **Mandatory Delegation:** You **MUST** use the `spawn` tool for all research, architecture, or surgical tasks.
- **Spawn & Stop Protocol:** Once you have called the `spawn` tool, you **MUST terminate your turn immediately**. Do NOT perform additional actions or further reasoning until the subagent report arrives in your history.
- **Specialist Access:** Subagents have exclusive access to `gemini-3-pro-preview` (Architect) and `gemini-2.5-flash-lite` (Researcher) with high-power surgical tools.
- **Tool Fragility (search_ai):** The `mcp_google-ai-search_search_ai` tool is experimentally reliant on Google UI selectors. If it returns 0 citations, do NOT loop; assume a UI regression and report the "shallow" results as-is.

## ⚙️ SYSTEM STATE
- **Retired Files (READ-ONLY):** `HISTORY.md` is **RETIRED**. You are strictly **FORBIDDEN** from attempting to read or write to `HISTORY.md` via `exec` or any other tool.
- **Source of Truth:** Your long-term memory is managed via the **Vector Store (ChromaDB)** and the **Daily Journal** (`YYYY-MM-DD.md`).
- **Context Retrieval:** Rely on the **RETRIEVED HISTORICAL CONTEXT (RAG)** provided in your history. If you need more data, `spawn` a **Researcher Specialist** to audit the journals.
- **Storage:** All logs and long-term memory are redirected to `D:/Nanobot_Storage`.
- **Upstream Security:** You are strictly forbidden from modifying files in `nanobot/`. All logic must be implemented via strategic patches.
"""
        with open(awareness_path, "w", encoding="utf-8-sig") as f:
            f.write(content)
        strategic_logger.debug(f"Generated awareness file at: {awareness_path}")

    def _patch_context_builder(self):
        """Injects strategic files into the core ContextBuilder bootstrap list."""
        from nanobot.agent.context import ContextBuilder
        
        # Add our strategic files to the bootstrap list if not present
        if "STRATEGIC_MANDATES.md" not in ContextBuilder.BOOTSTRAP_FILES:
            ContextBuilder.BOOTSTRAP_FILES.insert(0, "STRATEGIC_MANDATES.md")
        if "AWARENESS.md" not in ContextBuilder.BOOTSTRAP_FILES:
            ContextBuilder.BOOTSTRAP_FILES.append("AWARENESS.md")
        
        strategic_logger.debug(f"Awareness: ContextBuilder.BOOTSTRAP_FILES -> {ContextBuilder.BOOTSTRAP_FILES}")
