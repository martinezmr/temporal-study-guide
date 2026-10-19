"""Day 07.

    uv run python -m solutions.day07.run demo
    uv run python -m solutions.day07.run demo --break nyc-acc-01    # mock: that device rejects auth
    DEVICE_MODE=live uv run --env-file .env python -m solutions.day07.run demo
"""

import argparse

from solutions.day07.workflows import TASK_QUEUE, BackupConfigsWorkflow
from solutions.shared import mock_lab
from solutions.shared.activities import get_running_config, list_devices, save_backups
from solutions.shared.runner import connect, make_worker, run


async def main(argv: list[str]) -> None:
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["worker", "demo"])
    p.add_argument("--break", dest="broken", default=None, help="mock: make this device fail")
    a = p.parse_args(argv)

    client = await connect()
    worker = make_worker(client, TASK_QUEUE, [BackupConfigsWorkflow], [get_running_config, list_devices, save_backups])
    if a.cmd == "worker":
        await worker.run()
        return
    if a.broken:
        mock_lab.fail_next(a.broken, 1, kind="auth")
    async with worker:
        report = await client.execute_workflow(BackupConfigsWorkflow.run, id="d07-backup", task_queue=TASK_QUEUE)
        print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    run(main)
