import asyncio
from datetime import datetime, timedelta

from pydantic import BaseModel
from temporalio import activity, workflow

with workflow.unsafe.imports_passed_through():
    from solutions.shared.activities import get_device_facts

TASK_QUEUE = "solutions-day10"


class MaintenanceRequest(BaseModel):
    id: str
    device: str
    task: str  # e.g. "collect-facts", "clear-counters"


class MaintenanceTicket(BaseModel):
    id: str
    device: str
    task: str
    completed_at: datetime
    output: str


@activity.defn
async def run_maintenance_task(device: str, task: str) -> str:
    activity.logger.info("Running %s on %s", task, device)
    return f"{task} done on {device}"


@workflow.defn
class DeviceWatchWorkflow:
    def __init__(self) -> None:
        self.device = ""
        self.paused = False
        self.stopped = False
        self.queue: list[MaintenanceRequest] = []
        self.done: dict[str, MaintenanceTicket] = {}

    @workflow.run
    async def run(self, device: str, interval_seconds: int = 300) -> int:
        self.device = device
        while not self.stopped:
            await workflow.execute_activity(get_device_facts, device, start_to_close_timeout=timedelta(seconds=30))
            try:
                await workflow.wait_condition(lambda: bool(self.queue) or self.stopped,
                                              timeout=timedelta(seconds=interval_seconds))
            except asyncio.TimeoutError:
                continue
            while self.queue:  # drain requests one at a time
                req = self.queue.pop(0)
                output = await workflow.execute_activity(run_maintenance_task, args=[req.device, req.task],
                                                         start_to_close_timeout=timedelta(seconds=60))
                self.done[req.id] = MaintenanceTicket(id=req.id, device=req.device, task=req.task,
                                                      completed_at=workflow.now(), output=output)
        await workflow.wait_condition(workflow.all_handlers_finished)
        return len(self.done)

    @workflow.update
    async def request_maintenance(self, req: MaintenanceRequest) -> MaintenanceTicket:
        """Caller waits until the task has actually run, then gets the ticket back."""
        self.queue.append(req)
        await workflow.wait_condition(lambda: req.id in self.done)
        return self.done[req.id]

    @request_maintenance.validator
    def validate_maintenance(self, req: MaintenanceRequest) -> None:
        """Rejections raise at the caller and leave NO trace in history."""
        if req.device != self.device:
            raise ValueError(f"this workflow owns {self.device}, not {req.device}")
        if self.paused:
            raise ValueError("watch is paused")
        if req.id in self.done or any(q.id == req.id for q in self.queue):
            raise ValueError(f"duplicate request id {req.id}")

    @workflow.signal
    def pause(self) -> None:
        self.paused = True

    @workflow.signal
    def resume(self) -> None:
        self.paused = False

    @workflow.signal
    def stop(self) -> None:
        self.stopped = True
