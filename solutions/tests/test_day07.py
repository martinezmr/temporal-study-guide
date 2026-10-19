import os
from pathlib import Path

from solutions.day07.workflows import BackupConfigsWorkflow
from solutions.shared import mock_lab
from solutions.tests.helpers import time_skipping_env, wf_id, worker


async def test_partial_failure_still_backs_up_the_rest():
    mock_lab.fail_next("nyc-acc-01", 1, kind="auth")
    async with await time_skipping_env() as env:
        async with worker(env, "t", [BackupConfigsWorkflow]):
            report = await env.client.execute_workflow(BackupConfigsWorkflow.run, id=wf_id(), task_queue="t")
    assert report.failed == ["nyc-acc-01"]
    assert sorted(report.saved) == ["bos-acc-01", "bos-rtr-01", "nyc-rtr-01"]
    assert len(list(Path(os.environ["BACKUP_DIR"]).glob("*.cfg"))) == 3
