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
        
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        content = f"""# Environmental Awareness
- **Current Time:** {now}
- **Workspace Root:** {storage_root}
- **Strategic Edition:** v1.2 (Enforced Delegation)
- **Active Drive:** D:/ (High-Capacity Storage)
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
