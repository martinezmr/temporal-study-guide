"""One agent turn = one activity: send the conversation, get back text and/or tool calls."""

import json

from pydantic import BaseModel
from temporalio import activity

from solutions.shared import mock_lab, settings
from solutions.shared.llm import messages_create

SYSTEM = (
    "You troubleshoot Arista EOS networks. Use the tools to gather evidence; never guess device state. "
    "Tools are read-only. When you know the answer, reply with a short diagnosis and a suggested fix."
)


class AgentTurnInput(BaseModel):
    system: str = SYSTEM
    messages: list[dict]
    tools: list[dict]


class AgentTurnOutput(BaseModel):
    content: list[dict]  # Anthropic content blocks: {"type": "text"} / {"type": "tool_use"}
    stop_reason: str
    input_tokens: int = 0
    output_tokens: int = 0


@activity.defn
async def llm_step(turn: AgentTurnInput) -> AgentTurnOutput:
    if not settings.anthropic_key():
        return mock_turn(turn)
    resp = await messages_create(turn.system, turn.messages, tools=turn.tools, max_tokens=1024)
    usage = resp.get("usage", {})
    return AgentTurnOutput(content=resp["content"], stop_reason=resp.get("stop_reason", ""),
                           input_tokens=usage.get("input_tokens", 0), output_tokens=usage.get("output_tokens", 0))


def mock_turn(turn: AgentTurnInput) -> AgentTurnOutput:
    """A scripted 'model': check interfaces, then LLDP, then diagnose. Deterministic and offline."""
    question = turn.messages[0]["content"] if isinstance(turn.messages[0]["content"], str) else ""
    devices = [d for d in mock_lab.TOPOLOGY if d in question] or ["bos-acc-01"]
    uses: dict[str, dict] = {}
    results: dict[str, str] = {}
    for m in turn.messages:
        if isinstance(m["content"], list):
            for b in m["content"]:
                if b.get("type") == "tool_use":
                    uses[b["id"]] = b
                elif b.get("type") == "tool_result":
                    results[b["tool_use_id"]] = b.get("content", "")
    called = {(u["name"], u["input"].get("device")) for u in uses.values()}
    tokens = len(json.dumps(turn.messages)) // 4
    available = {t["name"] for t in turn.tools}
    for tool in ("get_interfaces", "get_lldp"):
        todo = [d for d in devices if (tool, d) not in called]
        if todo and tool in available:
            blocks = [{"type": "tool_use", "id": f"toolu_mock_{len(uses) + i}", "name": tool, "input": {"device": d}}
                      for i, d in enumerate(todo)]
            return AgentTurnOutput(content=[{"type": "text", "text": f"Checking {tool} on {', '.join(todo)}."},
                                            *blocks], stop_reason="tool_use", input_tokens=tokens, output_tokens=50)
    down = []
    for use_id, u in uses.items():
        if u["name"] == "get_interfaces" and use_id in results:
            try:
                statuses = json.loads(results[use_id])
            except json.JSONDecodeError:
                continue
            down += [f"{p} on {u['input']['device']}" for p, s in statuses.items() if s.get("linkStatus") == "disabled"]
    answer = (f"Diagnosis: {', '.join(down)} is administratively down, so the LLDP adjacency over it is missing. "
              "Suggested fix: `no shutdown` on that interface (needs approval)." if down
              else "Diagnosis: all checked interfaces are up and LLDP neighbors look correct.")
    return AgentTurnOutput(content=[{"type": "text", "text": answer}], stop_reason="end_turn",
                           input_tokens=tokens, output_tokens=60)
