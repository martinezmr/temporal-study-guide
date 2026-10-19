import json

from pydantic import BaseModel
from temporalio import activity

from solutions.shared import settings
from solutions.shared.llm import extract_json, messages_create, text_of
from solutions.shared.models import DriftReport


class Proposal(BaseModel):
    device: str
    lines: list[str]
    reasoning: str


SYSTEM = (
    "Propose the minimal Arista EOS configuration lines that bring the device back to intent. "
    'Reply with ONLY JSON: {"lines": ["..."], "reasoning": "<two sentences>"}. Never propose reloads, '
    "erasing config, or removing AAA."
)


@activity.defn
async def propose_remediation(report: DriftReport) -> Proposal:
    if not settings.anthropic_key():
        return Proposal(device=report.device, lines=list(report.missing_lines),
                        reasoning=f"Intent requires {len(report.missing_lines)} line(s) that are missing (mock analysis).")
    resp = await messages_create(SYSTEM, [{"role": "user", "content": json.dumps(report.model_dump())}], max_tokens=400)
    data = extract_json(text_of(resp))
    return Proposal(device=report.device, lines=data["lines"], reasoning=data["reasoning"])
