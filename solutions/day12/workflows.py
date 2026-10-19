from datetime import timedelta

from pydantic import BaseModel
from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from solutions.shared.activities import get_device_facts
    from solutions.shared.models import DeviceFacts

TASK_QUEUE = "solutions-day12"


class WatchInput(BaseModel):
    """Everything the workflow must remember across Continue-As-New."""

    device: str
    interval_seconds: int = 300
    max_loops_per_run: int = 100  # use 3 for the break-it exercise
    stop_after_checks: int | None = None  # for demos/tests; None = forever
    checks: int = 0
    runs: int = 0
    paused: bool = False
    last_facts: DeviceFacts | None = None


@workflow.defn
class DeviceWatchWorkflow:
    def __init__(self) -> None:
        self.s: WatchInput | None = None
        self.check_requested = False

    @workflow.run
    async def run(self, inp: WatchInput) -> WatchInput:
        self.s = inp
        self.s.runs += 1
        loops = 0
        while True:
            if self._done():
                return self.s
            if loops >= self.s.max_loops_per_run or workflow.info().is_continue_as_new_suggested():
                break
            await workflow.wait_condition(lambda: not self.s.paused)
            self.s.last_facts = await workflow.execute_activity(
                get_device_facts, self.s.device, start_to_close_timeout=timedelta(seconds=30))
            self.s.checks += 1
            loops += 1
            self.check_requested = False
            if self._done():
                return self.s
            try:
                await workflow.wait_condition(lambda: self.check_requested,
                                              timeout=timedelta(seconds=self.s.interval_seconds))
            except TimeoutError:
                pass
        # Let in-flight signal/update handlers finish so nothing is dropped, then start fresh.
        await workflow.wait_condition(workflow.all_handlers_finished)
        workflow.continue_as_new(self.s)

    def _done(self) -> bool:
        return self.s.stop_after_checks is not None and self.s.checks >= self.s.stop_after_checks

    @workflow.query
    def get_state(self) -> WatchInput:
        return self.s

    @workflow.signal
    def pause(self) -> None:
        self.s.paused = True

    @workflow.signal
    def resume(self) -> None:
        self.s.paused = False

    @workflow.signal
    def force_check(self) -> None:
        self.check_requested = True
