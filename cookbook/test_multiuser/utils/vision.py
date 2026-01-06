"""
Minimal vision utilities: summarize an image using llm (base64 data URL).

Falls back to filename-based caption if API is unavailable.
"""
import os
import base64
import json
from pathlib import Path
from typing import Optional, Dict, Any

try:
    from openai import OpenAI  # type: ignore
except Exception:
    OpenAI = None  # type: ignore

try:
    from .config_loader import get_config_value
except ImportError:
    # Fallback if import fails
    def get_config_value(key: str, default: Any = None) -> Any:
        return default


def _to_data_url(image_path: str) -> str:
    p = Path(image_path)
    mime = "image/png" if p.suffix.lower() in [".png"] else "image/jpeg"
    b64 = base64.b64encode(p.read_bytes()).decode("utf-8")
    return f"data:{mime};base64,{b64}"


def summarize_img(
    image_path: str,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
    temperature: float = 0.0,
) -> Dict[str, Any]:
    """
    Summarize an image: generate a description and extract objects with their positions.
    
    Returns a dictionary with:
    - "description": A brief sentence describing the environment/scene
    - "objects": A dict mapping object names to their position (direction-distance)
    """
    fallback_result = {
        "description": f"photo({Path(image_path).name})",
        "objects": {}
    }
    
    # Fallback if client is not available
    if OpenAI is None:
        return fallback_result

    # Priority: parameter > config file > environment variable
    api_key = api_key or get_config_value("vision_llm.api_key") or os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        return fallback_result

    base_url = base_url or get_config_value("vision_llm.base_url") or os.getenv("OPENAI_BASE_URL")
    model = model or get_config_value("vision_llm.model") or os.getenv("OPENAI_VISION_MODEL", os.getenv("OPENAI_MODEL", "gemini-2.5-pro"))

    try:
        client = OpenAI(api_key=api_key, base_url=base_url)
        data_url = _to_data_url(image_path)
        
        prompt = """Analyze this image and provide:
1. A brief one-sentence description of the environment/scene.
2. A JSON object mapping each visible object to its position.

Position format: "direction-distance" where:
- direction: front, back, left, right, up, down, or combinations like front-left, front-right, back-left, back-right, up-left, up-right, down-left, down-right
- distance: near, mid, far

Return your response in this exact JSON format:
{
    "description": "Your one-sentence scene description here",
    "objects": {
        "object_name_1": "direction-distance",
        "object_name_2": "direction-distance"
    }
}

Example:
{
    "description": "A modern living room with sunlight streaming through large windows",
    "objects": {
        "sofa": "front-near",
        "coffee_table": "front-mid",
        "window": "front-far",
        "lamp": "right-near",
        "bookshelf": "left-mid"
    }
}

Return ONLY the JSON object, no additional text or markdown."""

        user_content = [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": data_url}}
        ]

        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": user_content}],
            temperature=temperature,
        )
        
        text = resp.choices[0].message.content or ""
        print(f"[DEBUG]summarize_img raw response: {text}")
        
        # Parse JSON from response
        text = text.strip()
        # Remove markdown code blocks if present
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
        
        try:
            result = json.loads(text)
            if isinstance(result, dict):
                # Validate and normalize the result
                description = result.get("description", "")
                objects = result.get("objects", {})
                
                if not isinstance(description, str):
                    description = str(description) if description else ""
                
                if not isinstance(objects, dict):
                    objects = {}
                else:
                    # Normalize object names to lowercase
                    objects = {
                        str(k).lower().strip(): str(v).lower().strip()
                        for k, v in objects.items()
                        if k and v
                    }
                
                final_result = {
                    "description": description or f"photo({Path(image_path).name})",
                    "objects": objects
                }
                print(f"[DEBUG]summarize_img parsed: {final_result}")
                return final_result
        except json.JSONDecodeError as e:
            print(f"[WARNING] JSON parsing failed in summarize_img: {e}")
        
        return fallback_result
        
    except Exception as e:
        print(f"[WARNING] summarize_img failed: {e}")
        return fallback_result
