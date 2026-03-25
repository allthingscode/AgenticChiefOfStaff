import json
from pathlib import Path
from strategery.logic.config_logic import validate_strategic_config

def diagnostic():
    config_path = Path.home() / ".nanobot" / "config.json"
    with open(config_path, "r", encoding="utf-8-sig") as f:
        data = json.load(f)
    
    print("--- Raw Data ---")
    print(json.dumps(data.get("agents", {}).get("specialists"), indent=2))
    
    config = validate_strategic_config(data)
    print("\n--- Validated Config (Pydantic) ---")
    print(f"Specialists type: {type(config.agents.specialists)}")
    print(f"Specialists content: {config.agents.specialists}")
    
    # Simulate get_specialist_model
    specialist_type = "researcher"
    s_type = specialist_type if specialist_type in ["researcher", "architect"] else "researcher"
    model = config.agents.specialists.get(s_type, {}).get("model")
    print(f"\nResult for 'researcher': {model}")

if __name__ == "__main__":
    diagnostic()
