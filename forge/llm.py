"""Single LLM call helper for Skill Forge.

All LLM calls for the agent must go through this module. It is wired to
OpenRouter via the OpenAI Python SDK.
"""

from __future__ import annotations

import os
from typing import Final

from loguru import logger
from openai import OpenAI

BASE_URL: Final[str] = "https://openrouter.ai/api/v1"
DEFAULT_MODEL: Final[str] = "anthropic/claude-sonnet-4"


def llm_call(user_prompt: str, system_prompt: str, model: str = DEFAULT_MODEL) -> str:
    """Execute a single LLM chat completion and return the response text.

    Parameters
    ----------
    user_prompt:
        The user-facing portion of the prompt.
    system_prompt:
        The system message describing behavior and constraints.
    model:
        The OpenRouter model identifier to use.
    """
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY environment variable is not set.")

    client = OpenAI(base_url=BASE_URL, api_key=api_key)

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
    except Exception:
        logger.exception("LLM call failed.")
        raise

    try:
        content = response.choices[0].message.content
    except Exception:
        logger.exception("Unexpected response structure from LLM.")
        raise

    if content is None:
        logger.error("LLM returned empty content.")
        return ""

    return content

