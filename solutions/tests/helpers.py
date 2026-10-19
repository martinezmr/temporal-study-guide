"""Test helpers: environments with the pydantic converter, plus a worker with every device activity."""

import uuid
from concurrent.futures import ThreadPoolExecutor

from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from solutions.shared.activities import DEVICE_ACTIVITIES


async def time_skipping_env() -> WorkflowEnvironment:
    return await WorkflowEnvironment.start_time_skipping(data_converter=pydantic_data_converter)


async def local_env(**kwargs) -> WorkflowEnvironment:
    """A real dev server (downloaded once). Use for updates, update-with-start, Nexus, search attributes."""
    return await WorkflowEnvironment.start_local(data_converter=pydantic_data_converter, **kwargs)


def worker(env: WorkflowEnvironment, task_queue: str, workflows, activities=None, **kwargs) -> Worker:
    return Worker(env.client, task_queue=task_queue, workflows=list(workflows),
                  activities=list(activities if activities is not None else DEVICE_ACTIVITIES),
                  activity_executor=ThreadPoolExecutor(10), **kwargs)


def wf_id(prefix: str = "test") -> str:
    return f"{prefix}-{uuid.uuid4()}"
