import asyncio
from datetime import datetime, timedelta

from pydantic import BaseModel
from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from solutions.shared.activities import get_device_facts
    from solutions.shared.models import DeviceFacts

TASK_QUEUE = "solutions-day09"


class WatchStatus(BaseModel):
    device: str
    paused: bool
    checks: int
    last_checked: datetime | None = None
    last_facts: DeviceFacts | None = None


@workflow.defn
class DeviceWatchWorkflow:
    def __init__(self) -> None:
        self.device = ""
        self.paused = False
        self.check_requested = False
        self.stopped = False
        self.checks = 0
        self.last_checked: datetime | None = None
        self.last_facts: DeviceFacts | None = None

    @workflow.run
    async def run(self, device: str, interval_seconds: int = 300) -> WatchStatus:
        self.device = device
        while not self.stopped:
            await workflow.wait_condition(lambda: not self.paused or self.stopped)
            if self.stopped:
                break
            self.last_facts = await workflow.execute_activity(
                get_device_facts, device, start_to_close_timeout=timedelta(seconds=30))
            self.last_checked = workflow.now()
            self.checks += 1
            self.check_requested = False
            try:
                await workflow.wait_condition(lambda: self.check_requested or self.stopped,
                                              timeout=timedelta(seconds=interval_seconds))
            except asyncio.TimeoutError:
                pass
        return self.get_status()

    @workflow.query
    def get_status(self) -> WatchStatus:
        """Read-only. No awaits, no state changes, no activities."""
        return WatchStatus(device=self.device, paused=self.paused, checks=self.checks,
                           last_checked=self.last_checked, last_facts=self.last_facts)

    @workflow.signal
    def pause(self) -> None:
        self.paused = True

    @workflow.signal
    def resume(self) -> None:
        self.paused = False

    @workflow.signal
    def force_check(self) -> None:
        self.check_requested = True

    @workflow.signal
    def stop(self) -> None:
        self.stopped = True
