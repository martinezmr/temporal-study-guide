import asyncio
from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from solutions.shared.activities import get_device_facts

TASK_QUEUE = "solutions-day08"


@workflow.defn
class DeviceWatchWorkflow:
    def __init__(self) -> None:
        self.paused = False
        self.check_requested = False
        self.stopped = False
        self.checks = 0

    @workflow.run
    async def run(self, device: str, interval_seconds: int = 300) -> int:
        while not self.stopped:
            # Block here while paused (or until told to stop).
            await workflow.wait_condition(lambda: not self.paused or self.stopped)
            if self.stopped:
                break
            await workflow.execute_activity(get_device_facts, device, start_to_close_timeout=timedelta(seconds=30))
            self.checks += 1
            self.check_requested = False
            try:
                # Sleep until the interval passes OR someone asks for a check now.
                await workflow.wait_condition(lambda: self.check_requested or self.stopped,
                                              timeout=timedelta(seconds=interval_seconds))
            except asyncio.TimeoutError:
                pass  # the normal case: the interval elapsed
        return self.checks

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
        """Lets the demo (and tests) end the loop cleanly instead of terminating."""
        self.stopped = True

    @workflow.query
    def is_paused(self) -> bool:  # Day 9 expands on queries
        return self.paused

    @workflow.query
    def check_count(self) -> int:
        return self.checks
