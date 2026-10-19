from datetime import datetime

from pydantic import BaseModel
from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from solutions.shared.drift_cycle import collect_drift
    from solutions.shared.models import DriftReport

TASK_QUEUE = "solutions-day18"
SCHEDULE_ID = "d18-nightly-compliance-audit"


class AuditReport(BaseModel):
    ran_at: datetime
    compliant: list[str]
    drifted: list[DriftReport]
    unreachable: list[str]


@workflow.defn
class FullComplianceAuditWorkflow:
    """Stateless: every run starts from scratch. That's what makes it a Schedule, not a timer loop."""

    @workflow.run
    async def run(self) -> AuditReport:
        reports, unreachable = await collect_drift()
        return AuditReport(
            ran_at=workflow.now(),
            compliant=sorted(r.device for r in reports if not r.drifted),
            drifted=[r for r in reports if r.drifted],
            unreachable=unreachable,
        )
