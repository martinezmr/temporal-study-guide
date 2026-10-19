from datetime import timedelta

from temporalio import workflow
from temporalio.common import SearchAttributePair, TypedSearchAttributes

with workflow.unsafe.imports_passed_through():
    from solutions.day20.search_attributes import COMPLIANCE_STATE, DEVICE_NAME, SITE
    from solutions.shared.activities import compute_drift, get_intent, get_running_config, list_devices
    from solutions.shared.models import DriftReport

TASK_QUEUE = "solutions-day20"
ACT = {"start_to_close_timeout": timedelta(seconds=60)}


@workflow.defn
class DeviceComplianceCheckWorkflow:
    """One per device. Its search attributes make it findable: ComplianceState = "drifted" AND Site = "bos"."""

    @workflow.run
    async def run(self, device: str) -> DriftReport:
        workflow.upsert_search_attributes([COMPLIANCE_STATE.value_set("checking")])
        intent = await workflow.execute_activity(get_intent, device, **ACT)
        state = await workflow.execute_activity(get_running_config, device, **ACT)
        report = await workflow.execute_activity(compute_drift, args=[intent, state], **ACT)
        workflow.upsert_search_attributes([COMPLIANCE_STATE.value_set("drifted" if report.drifted else "compliant")])
        workflow.logger.info("%s -> %s", device, "drifted" if report.drifted else "compliant")  # replay-safe
        return report


@workflow.defn
class ComplianceSweepWorkflow:
    @workflow.run
    async def run(self) -> list[str]:
        devices = await workflow.execute_activity(list_devices, **ACT)
        handles = []
        for d in devices:
            intent = await workflow.execute_activity(get_intent, d, **ACT)
            handles.append(await workflow.start_child_workflow(
                DeviceComplianceCheckWorkflow.run, d,
                id=f"d20-check-{d}-{workflow.info().run_id[:8]}",
                search_attributes=TypedSearchAttributes([
                    SearchAttributePair(DEVICE_NAME, d), SearchAttributePair(SITE, intent.site)]),
                static_summary=f"Compliance check: {d} ({intent.site})",  # shown in the UI list and detail page
            ))
        reports = [await h for h in handles]
        return sorted(r.device for r in reports if r.drifted)
