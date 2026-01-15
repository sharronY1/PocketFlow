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
        
        prompt = """You are a helpful assistant that analyzes images and provides a description of the environment/scene and the objects in the image. Analyze this image and provide:
1. A brief one-sentence description of the environment/scene.
2. A JSON object mapping each visible object to its position.
The robots in your view is your a part of your avatar, you should not put robots into discovered objects.
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
                return final_result
        except json.JSONDecodeError as e:
            print(f"[WARNING] JSON parsing failed in summarize_img: {e}")
        
        return fallback_result
        
    except Exception as e:
        print(f"[WARNING] summarize_img failed: {e}")
        return fallback_result


def compare_img(
    prev_image_path: str,
    curr_image_path: str,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
    temperature: float = 0.0,
) -> str:
    """
    Compare two images and describe the changes/differences between them.
    
    Args:
        prev_image_path: Path to the previous screenshot (taken earlier)
        curr_image_path: Path to the current screenshot (taken now)
        api_key: OpenAI API key (optional, falls back to config/env)
        base_url: OpenAI API base URL (optional)
        model: Model name to use (optional)
        temperature: Sampling temperature
        
    Returns:
        A string describing the changes between the two images in English
    """
    fallback_result = "Unable to compare images."
    
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
        prev_data_url = _to_data_url(prev_image_path)
        curr_data_url = _to_data_url(curr_image_path)
        
        prompt = """You are given two consecutive screenshots from a 3D environment exploration.

Image 1 (PREVIOUS): The screenshot taken at the previous timestep.
Image 2 (CURRENT): The screenshot taken at the current timestep.

Please briefly summarize the changes or differences between these two images. Focus on:
1. Changes in viewpoint/camera position (e.g., moved forward, turned left)
2. Objects that appeared or disappeared from view
3. Any notable environmental changes

Be concise and factual. If the images are nearly identical, state that there are minimal changes.

Return ONLY a brief text description of the changes (1-3 sentences), no JSON or markdown formatting."""

        user_content = [
            {"type": "text", "text": prompt},
            {"type": "text", "text": "Image 1 (PREVIOUS):"},
            {"type": "image_url", "image_url": {"url": prev_data_url}},
            {"type": "text", "text": "Image 2 (CURRENT):"},
            {"type": "image_url", "image_url": {"url": curr_data_url}}
        ]

        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": user_content}],
            temperature=temperature,
        )
        
        text = resp.choices[0].message.content or ""
        text = text.strip()
        
        return text if text else fallback_result
        
    except Exception as e:
        print(f"[WARNING] compare_img failed: {e}")
        return fallback_result