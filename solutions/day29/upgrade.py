from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ApplicationError

with workflow.unsafe.imports_passed_through():
    from solutions.shared.activities import (
        check_image, get_device_facts, postcheck_compare, precheck_snapshot, simulate_reload,
    )
    from solutions.shared.models import UpgradeInput, UpgradeResult

ACT = {"start_to_close_timeout": timedelta(seconds=60), "retry_policy": RetryPolicy(maximum_attempts=3)}


@workflow.defn
class DeviceUpgradeWorkflow:
    """Real shape, simulated reload (cEOS can't be upgraded in place)."""

    def __init__(self) -> None:
        self.stage = "starting"
        self.emergency_override = False

    @workflow.run
    async def run(self, inp: UpgradeInput) -> UpgradeResult:
        d = inp.device
        self.stage = "pre-checks"
        before = await workflow.execute_activity(precheck_snapshot, d, **ACT)
        facts = await workflow.execute_activity(get_device_facts, d, **ACT)
        from_version = facts.version
        if from_version == inp.target_version:
            return UpgradeResult(device=d, upgraded=False, from_version=from_version, detail="already on target")
        if not await workflow.execute_activity(check_image, args=[d, inp.target_version], **ACT):
            raise ApplicationError(f"{d}: image {inp.target_version} not staged", type="ImageMissing", non_retryable=True)

        if not inp.skip_window:
            self.stage = "waiting for maintenance window"
            await self._wait_for_window(inp.tz_offset_hours)

        self.stage = "reloading"
        await workflow.execute_activity(simulate_reload, args=[d, inp.target_version], **ACT)

        self.stage = "waiting for device"
        for _ in range(20):  # up to ~10 minutes
            await workflow.sleep(30)
            try:
                facts = await workflow.execute_activity(get_device_facts, d, start_to_close_timeout=timedelta(seconds=20),
                                                        retry_policy=RetryPolicy(maximum_attempts=1))
                if facts.version == inp.target_version:
                    break
            except Exception:  # noqa: BLE001 - still rebooting
                continue
        else:
            raise ApplicationError(f"{d} did not come back on {inp.target_version}", type="UpgradeTimeout",
                                   non_retryable=True)

        self.stage = "post-checks"
        changed = await workflow.execute_activity(postcheck_compare, args=[d, before], **ACT)
        if changed:
            raise ApplicationError(f"{d}: LLDP changed after upgrade: {changed}", type="PostcheckFailed",
                                   non_retryable=True)
        self.stage = "done"
        return UpgradeResult(device=d, upgraded=True, from_version=from_version, to_version=inp.target_version)

    async def _wait_for_window(self, tz_offset_hours: int) -> None:
        local_now = workflow.now() + timedelta(hours=tz_offset_hours)
        window = local_now.replace(hour=2, minute=0, second=0, microsecond=0)
        if window <= local_now:
            window += timedelta(days=1)
        try:
            await workflow.wait_condition(lambda: self.emergency_override, timeout=window - local_now)
        except TimeoutError:
            pass

    @workflow.signal
    def override_window(self) -> None:
        self.emergency_override = True

    @workflow.query
    def progress(self) -> str:
        return self.stage
