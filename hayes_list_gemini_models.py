import google.genai as genai
import os
import sys

# 2026 Pricing Table (USD per 1 million tokens)
# Note: Prices for Pro models typically double if context > 200k.
PRICING = {
    "gemini-3-pro-preview": {"in": 2.00, "out": 12.00, "tier": "Flagship Reasoning"},
    "gemini-3-flash-preview": {"in": 0.50, "out": 3.00, "tier": "High-Speed Intelligence"},
    "gemini-2.5-pro": {"in": 1.25, "out": 10.00, "tier": "Balanced Pro"},
    "gemini-2.5-flash": {"in": 0.30, "out": 2.50, "tier": "Daily Driver"},
    "gemini-2.0-flash": {"in": 0.10, "out": 0.40, "tier": "Bulk/Efficiency"},
    "gemini-2.0-flash-lite": {"in": 0.075, "out": 0.30, "tier": "Ultra Low Cost"},
    "gemini-1.5-pro": {"in": 1.25, "out": 5.00, "tier": "Legacy Reasoning"},
    "gemini-1.5-flash": {"in": 0.075, "out": 0.30, "tier": "Legacy Speed"}
}

if "GOOGLE_AI_API_KEY" not in os.environ:
    print("ERROR: Run this first: set GOOGLE_AI_API_KEY=\"AI...\"", file=sys.stderr)
    sys.exit(1)

try:
    print(f"{'MODEL NAME':<30} | {'TIER':<20} | {'IN/1M':<8} | {'OUT/1M':<8}")
    print("-" * 75)
    
    client = genai.Client(api_key=os.environ["GOOGLE_AI_API_KEY"])
    
    for model in client.models.list():
        if 'generateContent' in model.supported_actions:
            # Clean name for matching (removes 'models/' prefix)
            clean_name = model.name.replace('models/', '')
            price = PRICING.get(clean_name, {"in": "N/A", "out": "N/A", "tier": "Other"})
            
            print(f"{clean_name:<30} | {price['tier']:<20} | ${price['in']:<7} | ${price['out']:<7}")

except Exception as e:
    print(f"Error: {e}", file=sys.stderr)