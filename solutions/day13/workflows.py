import asyncio
from datetime import timedelta
from typing import Literal

from pydantic import BaseModel
from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from solutions.shared.activities import get_device_facts, get_lldp

TASK_QUEUE = "solutions-day13"


class DeviceRequest(BaseModel):
    id: str
    action: Literal["facts", "lldp"]
    requested_by: str = "operator"


class RequestResult(BaseModel):
    id: str
    position: int  # order in which this entity processed it: proves serialization
    output: str


class DeviceEntityInput(BaseModel):
    device: str
    processed: int = 0
    idle_minutes: int = 60


@workflow.defn
class DeviceEntityWorkflow:
    """One per device. Workflow ID = f"device-{name}". The single owner of that device's changes."""

    def __init__(self) -> None:
        self.s: DeviceEntityInput | None = None
        self.queue: list[DeviceRequest] = []
        self.results: dict[str, RequestResult] = {}
        self.lock = asyncio.Lock()  # belt and braces if you ever run work from handlers

    @workflow.run
    async def run(self, inp: DeviceEntityInput) -> None:
        self.s = inp
        while not workflow.info().is_continue_as_new_suggested():
            try:
                await workflow.wait_condition(lambda: bool(self.queue), timeout=timedelta(minutes=self.s.idle_minutes))
            except TimeoutError:
                break  # idle: continue-as-new to keep history short
            req = self.queue.pop(0)
            async with self.lock:
                self.results[req.id] = await self.handle(req)
        await workflow.wait_condition(workflow.all_handlers_finished)
        workflow.continue_as_new(self.s)

    async def handle(self, req: DeviceRequest) -> RequestResult:
        if req.action == "facts":
            facts = await workflow.execute_activity(get_device_facts, self.s.device,
                                                    start_to_close_timeout=timedelta(seconds=30))
            output = f"version {facts.version}"
        else:
            nbrs = await workflow.execute_activity(get_lldp, self.s.device, start_to_close_timeout=timedelta(seconds=30))
            output = ", ".join(f"{n['port']}->{n['neighborDevice']}" for n in nbrs)
        self.s.processed += 1
        return RequestResult(id=req.id, position=self.s.processed, output=output)

    @workflow.update
    async def submit(self, req: DeviceRequest) -> RequestResult:
        self.queue.append(req)
        await workflow.wait_condition(lambda: req.id in self.results)
        return self.results.pop(req.id)

    @submit.validator
    def validate_submit(self, req: DeviceRequest) -> None:
        if any(q.id == req.id for q in self.queue):
            raise ValueError(f"duplicate request {req.id}")

    @workflow.query
    def queue_depth(self) -> int:
        return len(self.queue)
