"""Anthropic Messages API over plain HTTPS (no SDK dependency), with Temporal-friendly errors.

With ANTHROPIC_API_KEY unset, the activities in days 25-28 fall back to deterministic mocks,
so every demo and test runs offline. Set LLM_MODEL to choose the model.
"""

import json
import re

import niquests
from temporalio.exceptions import ApplicationError

from solutions.shared import settings

API_URL = "https://api.anthropic.com/v1/messages"


async def messages_create(system: str, messages: list[dict], tools: list[dict] | None = None,
                          max_tokens: int = 1024) -> dict:
    body: dict = {"model": settings.llm_model(), "max_tokens": max_tokens, "system": system, "messages": messages}
    if tools:
        body["tools"] = tools
    headers = {"x-api-key": settings.anthropic_key(), "anthropic-version": "2023-06-01",
               "content-type": "application/json"}
    async with niquests.AsyncSession() as s:
        resp = await s.post(API_URL, json=body, headers=headers, timeout=120)
    if resp.status_code == 429 or resp.status_code >= 500:
        # Retryable: rate limited or overloaded. The activity's retry policy backs off.
        raise RuntimeError(f"LLM API HTTP {resp.status_code}; will retry")
    if resp.status_code >= 400:
        # Bad request, bad key, prompt too long: retrying the same request won't help.
        raise ApplicationError(f"LLM API rejected the request: HTTP {resp.status_code}: {resp.text[:300]}",
                               type="LLMBadRequest", non_retryable=True)
    return resp.json()


def text_of(resp: dict) -> str:
    return "".join(b.get("text", "") for b in resp.get("content", []) if b.get("type") == "text")


def extract_json(text: str) -> dict:
    """Pull the first {...} object out of a model reply. Retryable on failure: the next sample may comply."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ApplicationError(f"model did not return JSON: {text[:200]!r}", type="BadModelOutput")
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError as e:
        raise ApplicationError(f"model returned invalid JSON: {e}", type="BadModelOutput") from e
