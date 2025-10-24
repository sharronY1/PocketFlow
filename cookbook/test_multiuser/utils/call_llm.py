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


def call_llm(
    prompt: str,
    api_key: Optional[str] = "sk-d7xl1uSrUhkgSdg9ciIhKBay5MDZlapxcZtlaGrOoE99VMoa",
    base_url: Optional[str] = "https://api.nuwaapi.com/v1",
    model: Optional[str] = "gpt-4o",
    temperature: float = 0.0,
) -> str:
    """
    Call OpenAI-compatible LLM and return the text response.

    Args:
        prompt: input prompt
        api_key: override API key (falls back to OPENAI_API_KEY)
        base_url: override base URL (falls back to OPENAI_BASE_URL)
        model: override model name (falls back to OPENAI_MODEL or default)
        temperature: sampling temperature (default 0.2)
    """
    api_key = api_key or os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    base_url = base_url or os.getenv("OPENAI_BASE_URL")
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

