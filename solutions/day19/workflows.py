"""Three versions of one workflow type, to practise patching.

v1        -> what's running in production today
v2        -> adds an LLDP check, guarded by workflow.patched(): safe for old histories
v2_bad    -> adds the same check without a patch: breaks old histories (the test proves it)
v3 (in comments) -> deprecate_patch once no v1 runs remain, then delete the branch
"""

from datetime import timedelta

from pydantic import BaseModel
from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from solutions.shared.activities import get_device_facts, get_lldp

TASK_QUEUE = "solutions-day19"
ACT = {"start_to_close_timeout": timedelta(seconds=30)}


class DeviceAudit(BaseModel):
    device: str
    version: str
    neighbors: int | None = None


@workflow.defn(name="DeviceAuditWorkflow")
class DeviceAuditV1:
    @workflow.run
    async def run(self, device: str) -> DeviceAudit:
        facts = await workflow.execute_activity(get_device_facts, device, **ACT)
        await workflow.sleep(60)  # gives you time to deploy v2 while v1 runs are in flight
        return DeviceAudit(device=device, version=facts.version)


@workflow.defn(name="DeviceAuditWorkflow")
class DeviceAuditV2:
    @workflow.run
    async def run(self, device: str) -> DeviceAudit:
        facts = await workflow.execute_activity(get_device_facts, device, **ACT)
        await workflow.sleep(60)
        neighbors = None
        if workflow.patched("add-lldp-check"):
            # New runs take this branch. Replays of old runs (no marker in history) skip it.
            neighbors = len(await workflow.execute_activity(get_lldp, device, **ACT))
        return DeviceAudit(device=device, version=facts.version, neighbors=neighbors)
        # v3, once every v1 run has finished:
        #   workflow.deprecate_patch("add-lldp-check")
        #   neighbors = len(await workflow.execute_activity(get_lldp, device, **ACT))
        # v4: delete the deprecate_patch line.


@workflow.defn(name="DeviceAuditWorkflow")
class DeviceAuditV2Bad:
    @workflow.run
    async def run(self, device: str) -> DeviceAudit:
        facts = await workflow.execute_activity(get_device_facts, device, **ACT)
        await workflow.sleep(60)
        neighbors = len(await workflow.execute_activity(get_lldp, device, **ACT))  # no patch: non-deterministic
        return DeviceAudit(device=device, version=facts.version, neighbors=neighbors)
