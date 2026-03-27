"""
F-043: Model Tier Auditor — Entry Point
Lists available Gemini models, classifies them into strategic tiers,
and writes a Markdown audit report comparing them against the current config.

Usage:
    nanoClaw/Scripts/python.exe strategery/evaluate_models.py

Output:
    - Prints report to stdout
    - Saves report to D:/Nanobot_Storage/workspace/model_tier_audit.md
"""
import json
import sys
from pathlib import Path

CONFIG_PATH = Path.home() / ".nanobot" / "config.json"
WORKSPACE = Path("D:/Nanobot_Storage/workspace")
REPORT_NAME = "model_tier_audit.md"


def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    config = load_config()

    api_key = config.get("providers", {}).get("gemini", {}).get("apiKey", "")
    if not api_key:
        print("ERROR: No Gemini API key in ~/.nanobot/config.json", file=sys.stderr)
        sys.exit(1)

    agents = config.get("agents", {})
    current = {
        "default":    agents.get("defaults", {}).get("model", "unknown"),
        "researcher": agents.get("specialists", {}).get("researcher", {}).get("model", "unknown"),
        "architect":  agents.get("specialists", {}).get("architect", {}).get("model", "unknown"),
    }

    try:
        from google import genai  # noqa: E402
        client = genai.Client(api_key=api_key)
        print("Fetching available models from Gemini API...", file=sys.stderr)
        models = list(client.models.list())
        print(f"Retrieved {len(models)} models.", file=sys.stderr)
    except Exception as e:
        print(f"ERROR: Gemini API call failed: {e}", file=sys.stderr)
        sys.exit(1)

    from strategery.logic.model_audit_logic import build_report  # noqa: E402
    report = build_report(models, current)

    # Save to workspace
    try:
        out_path = WORKSPACE / REPORT_NAME
        out_path.write_text(report, encoding="utf-8")
        print(f"Report saved to: {out_path}", file=sys.stderr)
    except Exception as e:
        print(f"WARNING: Could not save report to workspace: {e}", file=sys.stderr)

    print(report)


if __name__ == "__main__":
    main()
