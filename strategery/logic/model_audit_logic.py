"""
F-043: Model Tier Auditor — Pure Logic
Classifies Gemini models into strategic tiers and builds a Markdown audit report.
This module contains no I/O or API calls — all side effects live in evaluate_models.py.
"""
from datetime import date
from typing import Any


# Tier classification heuristics — order matters (most specific first)
_TIER_PATTERNS = [
    ("researcher", ["flash-lite"]),
    ("architect", ["pro", "ultra"]),
    ("default", ["flash"]),
]


def classify_model(model_name: str) -> str:
    """
    Classify a Gemini model into a strategic tier based on its name.

    Returns one of: 'researcher', 'default', 'architect', 'special', 'other'
    """
    name = model_name.lower().replace("models/", "")
    if any(x in name for x in ["embed", "aqa", "text-bison", "chat-bison", "vision",
                               "imagen", "veo", "lyria", "gemma", "robotics",
                               "computer-use", "deep-research", "tts", "audio"]):
        return "special"
    for tier, keywords in _TIER_PATTERNS:
        if any(kw in name for kw in keywords):
            return tier
    return "other"


def build_report(models: list[Any], current: dict[str, str]) -> str:
    """
    Build a Markdown audit report comparing available models against the current config.

    Args:
        models: List of model objects from the Gemini API (must have .name attribute).
        current: Dict with keys 'default', 'researcher', 'architect' and their model names.

    Returns:
        A Markdown-formatted report string.
    """
    today = date.today().isoformat()

    by_tier: dict[str, list] = {
        "researcher": [], "default": [], "architect": [], "special": [], "other": []
    }
    for m in models:
        by_tier[classify_model(m.name)].append(m)

    def _bare(name: str) -> str:
        return name.replace("models/", "")

    def _model_row(m: Any, current_name: str) -> str:
        bare = _bare(m.name)
        display = getattr(m, "display_name", bare) or bare
        desc = (getattr(m, "description", "") or "")[:90].replace("|", "\\|")
        flag = " **[CURRENT]**" if bare == _bare(current_name) else ""
        return f"| `{bare}` | {display}{flag} | {desc} |"

    lines = [
        "# F-043: Model Tier Audit Report",
        f"**Date:** {today}  ",
        f"**Available models:** {len(models)}",
        "",
        "---",
        "",
        "## Current Configuration",
        "",
        "| Role | Model |",
        "|------|-------|",
        f"| Default (Balanced) | `{current['default']}` |",
        f"| Researcher (Budget) | `{current['researcher']}` |",
        f"| Architect (Premium) | `{current['architect']}` |",
        "",
        "---",
        "",
    ]

    tier_sections = [
        ("researcher", "Researcher Tier — Budget (`flash-lite` candidates)", "researcher"),
        ("default",    "Default Tier — Balanced (`flash` candidates)",        "default"),
        ("architect",  "Architect Tier — Premium (`pro` / `ultra` candidates)", "architect"),
    ]

    suggestions: dict[str, str] = {}
    for tier_key, heading, config_key in tier_sections:
        tier_models = by_tier[tier_key]
        lines += [f"## {heading}", ""]
        if not tier_models:
            lines += ["*No models classified for this tier.*", ""]
            continue
        lines += ["| Model | Display Name | Notes |", "|-------|-------------|-------|"]
        for m in tier_models:
            lines.append(_model_row(m, current[config_key]))
        # Only suggest a replacement if the current model is NOT in the available list
        # (retirement awareness — not an automatic upgrade prompt)
        tier_bare_names = [_bare(m.name) for m in tier_models]
        current_bare = _bare(current[config_key])
        if current_bare not in tier_bare_names:
            suggestions[config_key] = tier_bare_names[0]
        lines.append("")

    # Special / embedding / other
    special_models = by_tier["special"] + by_tier["other"]
    lines += ["## Special-Purpose & Embedding Models", ""]
    if special_models:
        lines += ["| Model | Display Name |", "|-------|-------------|"]
        for m in special_models:
            bare = _bare(m.name)
            display = getattr(m, "display_name", bare) or bare
            lines.append(f"| `{bare}` | {display} |")
    else:
        lines.append("*None found.*")
    lines.append("")

    # Suggestions summary
    lines += ["---", "", "## Suggested Updates", ""]
    if suggestions:
        lines += [
            "| Role | Current | Candidate |",
            "|------|---------|-----------|",
        ]
        for role, candidate in suggestions.items():
            lines.append(f"| `{role}` | `{current[role]}` | `{candidate}` |")
        lines += [
            "",
            "> **No changes are applied automatically.**",
            "> Edit `~/.nanobot/config.json` to apply updates.",
        ]
    else:
        lines.append(
            "Current configuration already matches the best available candidates."
            " No changes suggested."
        )

    return "\n".join(lines)
