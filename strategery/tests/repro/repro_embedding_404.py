import asyncio
import os
import sys
from pathlib import Path

# Add project root to sys.path for strategery imports
project_root = Path(__file__).parent.parent.absolute()
sys.path.append(str(project_root))

from strategery.logic.provider_logic import run_strategic_embedding  # noqa: E402


async def list_models():
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        return

    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        print("\n--- Available Models ---")
        models = await client.aio.models.list()
        for model in models:
            actions = getattr(model, "supported_actions", "N/A")
            print(f"Name: {model.name}, Actions: {actions}")
    except Exception as e:
        print(f"EXCEPTION listing models: {e}")


async def test_embeddings():
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        return

    test_models = [
        "models/text-embedding-004",  # Should trigger fallback
        "models/gemini-embedding-001",
        "models/gemini-embedding-2-preview"
    ]

    for model in test_models:
        print(f"\n--- Testing Model: {model} ---")
        try:
            result = await run_strategic_embedding(api_key, model, "Strategic Intelligence Test")
            if result and len(result) > 0:
                print(f"SUCCESS: Received embedding of length {len(result[0])}")
            else:
                print("FAILURE: Received empty result.")
        except Exception as e:
            print(f"EXCEPTION: {e}")


if __name__ == "__main__":
    asyncio.run(list_models())
    asyncio.run(test_embeddings())
