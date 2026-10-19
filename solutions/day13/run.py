"""Day 13.

    uv run python -m solutions.day13.run worker
    uv run python -m solutions.day13.run burst bos-rtr-01 --count 10    # 10 concurrent requests, processed in order
"""

import argparse
import asyncio

from solutions.day13.client import submit_to_device
from solutions.day13.workflows import TASK_QUEUE, DeviceEntityWorkflow, DeviceRequest
from solutions.shared.activities import get_device_facts, get_lldp
from solutions.shared.runner import connect, make_worker, run


async def main(argv: list[str]) -> None:
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["worker", "burst"])
    p.add_argument("device", nargs="?", default="bos-rtr-01")
    p.add_argument("--count", type=int, default=10)
    a = p.parse_args(argv)

    client = await connect()
    if a.cmd == "worker":
        await make_worker(client, TASK_QUEUE, [DeviceEntityWorkflow], [get_device_facts, get_lldp]).run()
        return
    reqs = [DeviceRequest(id=f"req-{i}", action="facts" if i % 2 else "lldp") for i in range(a.count)]
    results = await asyncio.gather(*[submit_to_device(client, a.device, r) for r in reqs])
    for r in sorted(results, key=lambda r: r.position):
        print(f"#{r.position:2} {r.id:7} {r.output}")


if __name__ == "__main__":
    run(main)
