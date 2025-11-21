"""
LLM utility - OpenAI Chat Completions API
Supports custom operator base URL and API key via parameters or env vars.
"""
import os
from typing import List, Dict, Any, Optional

try:
    # openai>=1.0 modern client
    from openai import OpenAI  # type: ignore
except Exception:  # pragma: no cover
    OpenAI = None  # fallback for environments without openai installed

try:
    from .config_loader import get_config_value
except ImportError:
    # Fallback if import fails
    def get_config_value(key: str, default: Any = None) -> Any:
        return default


def call_llm(
    prompt: str,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
    temperature: float = 0.0,
) -> str:
    """
    Call OpenAI-compatible LLM and return the text response.

    Args:
        prompt: input prompt
        api_key: override API key (falls back to config.json, then OPENAI_API_KEY)
        base_url: override base URL (falls back to config.json, then OPENAI_BASE_URL)
        model: override model name (falls back to config.json, then OPENAI_MODEL)
        temperature: sampling temperature (default 0.0)
    """
    # Priority: parameter > config file > environment variable
    api_key = api_key or get_config_value("llm.api_key") or os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError("API key is not set in parameters, config.json, or OPENAI_API_KEY environment variable")

    model = model or get_config_value("llm.model") or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    base_url = base_url or get_config_value("llm.base_url") or os.getenv("OPENAI_BASE_URL")
    organization = os.getenv("OPENAI_ORG")

    if OpenAI is None:
        raise RuntimeError("openai package not installed. Please `pip install openai`.")

    # base_url and organization are optional and may be None
    client = OpenAI(api_key=api_key, base_url=base_url, organization=organization)

    # Use chat.completions for a single-turn message
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
    )

    text = resp.choices[0].message.content or ""
    return text


if __name__ == "__main__":
    # Simple connectivity test
    test_prompt = (
        "You are an exploration agent. You currently see: [\"chair\", \"table\"]\n\n"
        "Decide the next action:\n- forward: move to explore new area\n- backward: move back to re-check\n\n"
        "Output format (YAML):\n```yaml\nthinking: your reasoning\naction: forward or backward\nreason: why you chose this action\n```"
    )

    print("Testing LLM call (OpenAI)...")
    try:
        response = call_llm(test_prompt)
        print(f"Response:\n{response}")
    except Exception as e:
        print(f"OpenAI call failed: {e}")

