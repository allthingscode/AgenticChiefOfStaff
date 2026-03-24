import os
import warnings
from pathlib import Path
from typing import Any

with warnings.catch_warnings():
    warnings.simplefilter("ignore", FutureWarning)
    import google.generativeai as genai
from PIL import Image

from nanobot.agent.tools.base import Tool
from strategery.strategic_logger import strategic_logger

class MultimodalAnalyzerTool(Tool):
    """Tool for subagents to perform OCR and vision tasks on images."""
    
    def __init__(self, model_name: str = "models/gemini-2.0-flash"):
        super().__init__()
        self._model_name = model_name

    @property
    def name(self) -> str:
        return "mcp_multimodal_analyzer_analyze_image"

    @property
    def description(self) -> str:
        return "Analyzes an image or document from the D: drive and returns extracted text (OCR) or visual analysis based on the prompt."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "The absolute path to the file on the D: drive to analyze."
                },
                "prompt": {
                    "type": "string",
                    "description": "The specific question or instruction for analyzing the image (e.g., 'Extract all text' or 'What is the cheapest cocktail?')."
                }
            },
            "required": ["file_path", "prompt"]
        }

    async def execute(self, **kwargs: Any) -> str:
        file_path = kwargs.get("file_path")
        prompt = kwargs.get("prompt")
        
        if not file_path or not prompt:
            return "ERROR: Missing 'file_path' or 'prompt' parameter."
            
        path = Path(file_path)
        if not path.exists() or not path.is_file():
            return f"ERROR: File not found at '{file_path}'"

        try:
            # We assume api_key is available in the environment
            api_key = os.environ.get("GEMINI_API_KEY")
            if not api_key:
                return "ERROR: GEMINI_API_KEY environment variable is not set."
                
            genai.configure(api_key=api_key)
            
            # Open the image using PIL
            try:
                img = Image.open(path)
            except Exception as e:
                return f"ERROR: Failed to open image: {str(e)}"
                
            # Use the model assigned to the agent
            # Ensure model name includes 'models/' prefix if missing
            model_id = self._model_name
            if not model_id.startswith("models/"):
                model_id = f"models/{model_id}"
                
            model = genai.GenerativeModel(model_id) 
            
            response = await model.generate_content_async([prompt, img])
            return response.text or "No content returned by the vision model."
            
        except Exception as e:
            strategic_logger.error(f"Vision tool error: {e}")
            return f"ERROR analyzing image: {str(e)}"
