"""Day 15 stubs. Day 17 replaces ConfigComplianceWorkflow with the real saga; Day 29 replaces the upgrade."""

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from solutions.shared.models import ComplianceInput, ComplianceResult, UpgradeInput, UpgradeResult


@workflow.defn(name="ConfigComplianceWorkflow")
class ConfigComplianceStub:
    @workflow.run
    async def run(self, inp: ComplianceInput) -> ComplianceResult:
        workflow.logger.info("Would remediate %s: %s", inp.device, inp.missing_lines)
        await workflow.sleep(30)
        return ComplianceResult(device=inp.device, applied=False, detail="stub")


@workflow.defn(name="DeviceUpgradeWorkflow")
class DeviceUpgradeStub:
    @workflow.run
    async def run(self, inp: UpgradeInput) -> UpgradeResult:
        workflow.logger.info("Would upgrade %s to %s", inp.device, inp.target_version)
        await workflow.sleep(30)
        return UpgradeResult(device=inp.device, upgraded=False, detail="stub")
