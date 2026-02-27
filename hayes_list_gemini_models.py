import google.genai as genai
import os
import sys
import json
from pathlib import Path

# 2026 Pricing Table (USD per 1 million tokens)
# Note: Prices for Pro models typically double if context > 200k.
PRICING = {
    "gemini-3.1-pro-preview": {"in": 2.00, "out": 12.00, "tier": "Flagship Reasoning"},
    "gemini-3-pro-preview": {"in": 2.00, "out": 12.00, "tier": "Flagship Reasoning"},
    "gemini-3-flash-preview": {"in": 0.50, "out": 3.00, "tier": "High-Speed Intelligence"},
    "gemini-2.5-pro": {"in": 1.25, "out": 10.00, "tier": "Balanced Pro"},
    "gemini-2.5-flash": {"in": 0.30, "out": 2.50, "tier": "Daily Driver"},
    "gemini-2.5-flash-lite": {"in": 0.10, "out": 0.40, "tier": "Ultra Low Cost"},
    "gemini-2.0-flash": {"in": 0.10, "out": 0.40, "tier": "Bulk/Efficiency"},
    "gemini-2.0-flash-lite": {"in": 0.075, "out": 0.30, "tier": "Legacy Ultra Low"},
    "gemini-1.5-pro": {"in": 1.25, "out": 5.00, "tier": "Legacy Reasoning"},
    "gemini-1.5-flash": {"in": 0.075, "out": 0.30, "tier": "Legacy Speed"}
}

def get_price_info(model_name):
    # Clean name for matching (removes 'models/' prefix)
    clean_name = model_name.replace('models/', '')
    
    # Try exact match
    if clean_name in PRICING:
        return PRICING[clean_name]
    
    # Try fuzzy match (e.g. gemini-2.0-flash-001 -> gemini-2.0-flash)
    for key in PRICING:
        if clean_name.startswith(key):
            return PRICING[key]
            
    return {"in": "N/A", "out": "N/A", "tier": "Other"}

def get_api_key():
    # Priority 1: Environment Variable
    if "GOOGLE_AI_API_KEY" in os.environ:
        return os.environ["GOOGLE_AI_API_KEY"]
    
    # Priority 2: Nanobot Config
    config_path = Path.home() / ".nanobot" / "config.json"
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                return config.get("providers", {}).get("gemini", {}).get("apiKey")
        except Exception as e:
            print(f"Warning: Failed to read config from {config_path}: {e}", file=sys.stderr)
            
    return None

api_key = get_api_key()

if not api_key:
    print("ERROR: API key not found in GOOGLE_AI_API_KEY or C:\\Users\\HayesChiefOfStaff\\.nanobot\\config.json", file=sys.stderr)
    sys.exit(1)

try:
    print(f"{'MODEL NAME':<32} | {'TIER':<20} | {'IN/1M':<7} | {'OUT/1M':<7} | {'CTX LIMIT':<10}")
    print("-" * 90)
    
    client = genai.Client(api_key=api_key)
    
    # Sort models by name for better readability
    models = sorted(list(client.models.list()), key=lambda m: m.name)

    for model in models:
        if 'generateContent' in model.supported_actions:
            clean_name = model.name.replace('models/', '')
            price = get_price_info(model.name)
            
            # Use a fallback for tokens if not present
            ctx_limit = getattr(model, 'input_token_limit', 'N/A')
            
            print(f"{clean_name:<32} | {price['tier']:<20} | ${price['in']:<6} | ${price['out']:<6} | {ctx_limit:<10}")
            if price['tier'] == "Other" and hasattr(model, 'description') and model.description:
                # Wrap description for "Other" models to help identify them
                desc = model.description.strip()
                if len(desc) > 85:
                    desc = desc[:82] + "..."
                print(f"  └─ {desc}")

except Exception as e:
    print(f"Error: {e}", file=sys.stderr)