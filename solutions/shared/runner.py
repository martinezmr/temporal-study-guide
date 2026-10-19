"""Small helpers so each day's run.py stays short."""

import asyncio
import logging
import sys
from concurrent.futures import ThreadPoolExecutor

from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.worker import Worker

from solutions.shared import settings


async def connect(namespace: str | None = None, **kwargs) -> Client:
    return await Client.connect(
        settings.temporal_address(),
        namespace=namespace or settings.temporal_namespace(),
        data_converter=pydantic_data_converter,
        **kwargs,
    )


def make_worker(client: Client, task_queue: str, workflows=(), activities=(), **kwargs) -> Worker:
    kwargs.setdefault("activity_executor", ThreadPoolExecutor(max_workers=20))
    return Worker(client, task_queue=task_queue, workflows=list(workflows), activities=list(activities), **kwargs)


def run(main) -> None:
    """asyncio.run(main(sys.argv[1:])) with logging configured."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        asyncio.run(main(sys.argv[1:]))
    except KeyboardInterrupt:
        pass
