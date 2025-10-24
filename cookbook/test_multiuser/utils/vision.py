"""
Minimal vision utilities: caption an image using OpenAI (base64 data URL).

Falls back to filename-based caption if API is unavailable.
"""
import os
import base64
from pathlib import Path
from typing import Optional

try:
    from openai import OpenAI  # type: ignore
except Exception:
    OpenAI = None  # type: ignore


def _to_data_url(image_path: str) -> str:
    p = Path(image_path)
    mime = "image/png" if p.suffix.lower() in [".png"] else "image/jpeg"
    b64 = base64.b64encode(p.read_bytes()).decode("utf-8")
    return f"data:{mime};base64,{b64}"


def caption_image(
    image_path: str,
    prompt: Optional[str] = None,
    api_key: Optional[str] = "sk-emoNOZW80N1emlK5LxxfntmxxqyFyJEdT18PA3AUWin9qgkx",
    base_url: Optional[str] = "https://api.xinyun.ai/v1",
    model: Optional[str] = "gemini-2.5-pro",
    temperature: float = 0.0,
) -> str:
    """
    Return a short caption for the image. Uses OpenAI vision if available; otherwise returns a filename-based fallback.
    """
    # Fallback if client is not available
    if OpenAI is None:
        return f"photo({Path(image_path).name})"

    api_key = api_key or os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        return f"photo({Path(image_path).name})"

    base_url = base_url or os.getenv("OPENAI_BASE_URL")
    model = model or os.getenv("OPENAI_VISION_MODEL", os.getenv("OPENAI_MODEL", "gemini-2.5-pro"))

    try:
        client = OpenAI(api_key=api_key, base_url=base_url)
        data_url = _to_data_url(image_path)
        user_content = []
        if prompt:
            user_content.append({"type": "text", "text": prompt})
        else:
            user_content.append({"type": "text", "text": "Briefly describe this scene in one short sentence."})
        user_content.append({"type": "image_url", "image_url": {"url": data_url}})

        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": user_content}],
            temperature=0.2,
        )
        text = resp.choices[0].message.content or ""
        print(f"[DEBUG]caption_image: {text}")
        return text.strip() or f"photo({Path(image_path).name})"
    except Exception:
        return f"photo({Path(image_path).name})"


