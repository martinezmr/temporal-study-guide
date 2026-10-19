from solutions.day18.workflows import FullComplianceAuditWorkflow
from solutions.tests.helpers import time_skipping_env, wf_id, worker


async def test_audit_report():
    async with await time_skipping_env() as env:
        async with worker(env, "t", [FullComplianceAuditWorkflow]):
            r = await env.client.execute_workflow(FullComplianceAuditWorkflow.run, id=wf_id(), task_queue="t")
    assert r.compliant == ["bos-rtr-01", "nyc-acc-01"]
    assert sorted(d.device for d in r.drifted) == ["bos-acc-01", "nyc-rtr-01"]
