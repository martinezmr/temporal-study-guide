"""The durable agent loop. Called from workflow code; every model call and tool call is an activity."""

import asyncio
import json
from datetime import timedelta

from pydantic import BaseModel
from temporalio import workflow
from temporalio.common import RetryPolicy

from solutions.day26.llm_step import AgentTurnInput, llm_step
from solutions.day26.tools import TOOLS, tool_spec

LLM_RETRY = RetryPolicy(initial_interval=timedelta(seconds=5), maximum_attempts=4,
                        non_retryable_error_types=["LLMBadRequest"])


class AgentInput(BaseModel):
    question: str
    max_turns: int = 8
    token_budget: int = 60_000


class AgentResult(BaseModel):
    answer: str
    turns: int
    tokens: int
    tool_calls: list[str] = []
    stopped_by: str = "answer"  # answer | max_turns | token_budget


async def run_agent(inp: AgentInput, tool_names: list[str]) -> AgentResult:
    specs = [tool_spec(n) for n in tool_names]
    messages: list[dict] = [{"role": "user", "content": inp.question}]
    tokens, calls = 0, []
    for turn in range(1, inp.max_turns + 1):
        out = await workflow.execute_activity(llm_step, AgentTurnInput(messages=messages, tools=specs),
                                              start_to_close_timeout=timedelta(seconds=120), retry_policy=LLM_RETRY)
        tokens += out.input_tokens + out.output_tokens
        messages.append({"role": "assistant", "content": out.content})
        tool_uses = [b for b in out.content if b.get("type") == "tool_use"]
        if not tool_uses:
            answer = "".join(b.get("text", "") for b in out.content if b.get("type") == "text")
            return AgentResult(answer=answer, turns=turn, tokens=tokens, tool_calls=calls)
        if tokens > inp.token_budget:  # guardrail: cost cap
            return AgentResult(answer="Stopped: token budget exhausted.", turns=turn, tokens=tokens,
                               tool_calls=calls, stopped_by="token_budget")
        results = await asyncio.gather(*[_run_tool(b, tool_names) for b in tool_uses])
        calls += [f"{b['name']}({json.dumps(b.get('input', {}), sort_keys=True)})" for b in tool_uses]
        messages.append({"role": "user", "content": results})
    return AgentResult(answer="Stopped: too many turns without an answer.", turns=inp.max_turns, tokens=tokens,
                       tool_calls=calls, stopped_by="max_turns")


async def _run_tool(block: dict, allowed: list[str]) -> dict:
    name, args = block["name"], block.get("input", {})
    if name not in allowed:
        return {"type": "tool_result", "tool_use_id": block["id"], "is_error": True, "content": f"unknown tool {name}"}
    fn, arg_names, _ = TOOLS[name]
    try:
        result = await workflow.execute_activity(fn, args=[args[k] for k in arg_names],
                                                 start_to_close_timeout=timedelta(seconds=30),
                                                 retry_policy=RetryPolicy(maximum_attempts=3))
        return {"type": "tool_result", "tool_use_id": block["id"], "content": json.dumps(result, default=str)}
    except Exception as e:  # noqa: BLE001 - report tool failures back to the model instead of failing the workflow
        cause = getattr(e, "cause", None) or e  # ActivityError wraps the activity's own error
        return {"type": "tool_result", "tool_use_id": block["id"], "is_error": True, "content": str(cause)}
