from datetime import datetime, timedelta

from pydantic import BaseModel
from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from solutions.shared.activities import get_device_facts, get_lldp

TASK_QUEUE = "solutions-day04"
ACT = {"start_to_close_timeout": timedelta(seconds=30)}


class QuietHoursInput(BaseModel):
    device: str
    pause_seconds: int = 0  # set to 60 for the break-it exercise


class QuietHoursResult(BaseModel):
    device: str
    version: str
    neighbors: int
    quiet_hours: bool
    check_id: str
    jitter: int


@workflow.defn
class QuietHoursWorkflow:
    @workflow.run
    async def run(self, inp: QuietHoursInput) -> QuietHoursResult:
        now = workflow.now()  # replay-safe: the time recorded for this workflow task
        quiet = now.hour < 6
        facts = await workflow.execute_activity(get_device_facts, inp.device, **ACT)
        if inp.pause_seconds:
            await workflow.sleep(inp.pause_seconds)
        neighbors = await workflow.execute_activity(get_lldp, inp.device, **ACT)
        if quiet:
            workflow.logger.info("Inside quiet hours for %s", inp.device)  # not re-logged on replay
        return QuietHoursResult(
            device=inp.device,
            version=facts.version,
            neighbors=len(neighbors),
            quiet_hours=quiet,
            check_id=str(workflow.uuid4()),  # replay-safe UUID
            jitter=workflow.random().randint(0, 10),  # replay-safe random
        )


@workflow.defn(name="QuietHoursWorkflow")
class QuietHoursReordered:
    """The 'bad deploy': same workflow type, activities swapped. Replaying old histories fails."""

    @workflow.run
    async def run(self, inp: QuietHoursInput) -> QuietHoursResult:
        now = workflow.now()
        neighbors = await workflow.execute_activity(get_lldp, inp.device, **ACT)
        if inp.pause_seconds:
            await workflow.sleep(inp.pause_seconds)
        facts = await workflow.execute_activity(get_device_facts, inp.device, **ACT)
        return QuietHoursResult(device=inp.device, version=facts.version, neighbors=len(neighbors),
                                quiet_hours=now.hour < 6, check_id=str(workflow.uuid4()),
                                jitter=workflow.random().randint(0, 10))


@workflow.defn
class BrokenClockWorkflow:
    """Don't do this. The sandbox blocks datetime.now(); the workflow task fails and retries forever."""

    @workflow.run
    async def run(self) -> str:
        return datetime.now().isoformat()
