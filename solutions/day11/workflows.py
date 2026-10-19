from datetime import timedelta

from pydantic import BaseModel
from temporalio import workflow

TASK_QUEUE = "solutions-day11"


class WindowInput(BaseModel):
    device: str
    tz_offset_hours: int = -5  # America/Chicago in CDT; pass the site's offset from Nautobot later
    window_hour: int = 2  # 02:00 local


class WindowResult(BaseModel):
    device: str
    reason: str  # "window" or "override"
    waited_minutes: int


@workflow.defn
class MaintenanceWindowWorkflow:
    def __init__(self) -> None:
        self.emergency_override = False

    @workflow.run
    async def run(self, inp: WindowInput) -> WindowResult:
        started = workflow.now()
        reason = await self.wait_for_maintenance_window(inp)
        waited = int((workflow.now() - started).total_seconds() // 60)
        workflow.logger.info("%s: proceeding (%s) after %d min", inp.device, reason, waited)
        # ...the real change would run here (Day 17 / capstone)
        return WindowResult(device=inp.device, reason=reason, waited_minutes=waited)

    async def wait_for_maintenance_window(self, inp: WindowInput) -> str:
        local_now = workflow.now() + timedelta(hours=inp.tz_offset_hours)
        window = local_now.replace(hour=inp.window_hour, minute=0, second=0, microsecond=0)
        if window <= local_now:
            window += timedelta(days=1)
        try:
            # A durable timer racing a condition: survives worker and server restarts.
            await workflow.wait_condition(lambda: self.emergency_override, timeout=window - local_now)
            return "override"
        except TimeoutError:
            return "window"

    @workflow.signal
    def override(self) -> None:
        self.emergency_override = True
