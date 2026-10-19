"""A Worker Versioning-enabled worker.

    BUILD_ID=a1 VERSION=1 uv run python -m solutions.day19.worker
    BUILD_ID=b2 VERSION=2 uv run python -m solutions.day19.worker      # alongside the first one
See rollout.sh for the CLI steps between them.
"""

import os

from temporalio.common import VersioningBehavior, WorkerDeploymentVersion
from temporalio.worker import WorkerDeploymentConfig

from solutions.day19.workflows import TASK_QUEUE, DeviceAuditV1, DeviceAuditV2
from solutions.shared.activities import get_device_facts, get_lldp
from solutions.shared.runner import connect, make_worker, run

DEPLOYMENT_NAME = "netops-solutions"


async def main(argv: list[str]) -> None:
    build_id = os.environ.get("BUILD_ID", "dev")
    workflow_cls = DeviceAuditV2 if os.environ.get("VERSION", "1") == "2" else DeviceAuditV1
    client = await connect()
    worker = make_worker(
        client, TASK_QUEUE, [workflow_cls], [get_device_facts, get_lldp],
        deployment_config=WorkerDeploymentConfig(
            version=WorkerDeploymentVersion(deployment_name=DEPLOYMENT_NAME, build_id=build_id),
            use_worker_versioning=True,
            # Short audits finish on the build they started on.
            # (The long-lived orchestrator would use VersioningBehavior.AUTO_UPGRADE + patches.)
            default_versioning_behavior=VersioningBehavior.PINNED,
        ),
    )
    print(f"worker {DEPLOYMENT_NAME}:{build_id} running {workflow_cls.__name__}")
    await worker.run()


if __name__ == "__main__":
    run(main)
