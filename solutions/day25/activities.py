import json

from temporalio import activity

from solutions.shared import settings
from solutions.shared.llm import extract_json, messages_create, text_of
from solutions.shared.models import DriftExplanation, DriftReport

SYSTEM = (
    "You are a senior network engineer reviewing configuration drift on Arista EOS devices. "
    "Reply with ONLY a JSON object: "
    '{"summary": "<one sentence>", "risk": "low|medium|high", "likely_cause": "<one sentence>"}. '
    "Risk: low = logging/NTP/descriptions; medium = AAA, SNMP, software version; high = ACLs, routing, interfaces."
)


def mock_explanation(report: DriftReport) -> DriftExplanation:
    """Deterministic stand-in used when no API key is configured."""
    lines = " ".join(report.missing_lines)
    if any(k in lines for k in ("access-list", "route", "router ", "interface")):
        risk = "high"
    elif "aaa" in lines or "snmp" in lines or report.version_drift:
        risk = "medium"
    else:
        risk = "low"
    parts = []
    if report.missing_lines:
        parts.append(f"missing {len(report.missing_lines)} required line(s): {', '.join(report.missing_lines)}")
    if report.version_drift:
        parts.append(f"running {report.running_version}, intent is {report.target_version}")
    return DriftExplanation(device=report.device, summary=f"{report.device} is " + "; ".join(parts) + ".",
                            risk=risk, likely_cause="Manual change on the device or a missed rollout (mock analysis).")


@activity.defn
async def explain_drift(report: DriftReport) -> DriftExplanation:
    if not settings.anthropic_key():
        return mock_explanation(report)
    resp = await messages_create(
        SYSTEM,
        [{"role": "user", "content": json.dumps({
            "device": report.device, "missing_lines": report.missing_lines,
            "running_version": report.running_version, "target_version": report.target_version})}],
        max_tokens=300,
    )
    data = extract_json(text_of(resp))
    return DriftExplanation(device=report.device, **data)
