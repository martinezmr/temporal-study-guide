"""CI gate: replay every exported history against the current code. Exit 1 on any non-determinism.

    uv run python -m solutions.day30.replay_histories tests/histories

Export histories from a staging/lab environment, e.g.:
    temporal workflow show --workflow-id capstone-upgrade-nyc-rtr-01 -o json > tests/histories/upgrade-1.json
"""

import asyncio
import sys
from pathlib import Path

from temporalio.client import WorkflowHistory
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.worker import Replayer

from solutions.day29.workers import CAPSTONE_WORKFLOWS


async def replay_dir(directory: str) -> list[tuple[str, str]]:
    files = sorted(Path(directory).glob("*.json"))
    if not files:
        print(f"no histories in {directory}; nothing to replay")
        return []
    histories = [WorkflowHistory.from_json(f.stem, f.read_text()) for f in files]
    replayer = Replayer(workflows=CAPSTONE_WORKFLOWS, data_converter=pydantic_data_converter)
    results = await replayer.replay_workflows(histories, raise_on_replay_failure=False)
    failures = [(wid, repr(err)) for wid, err in results.replay_failures.items()]
    for f in files:
        print(f"{'FAIL' if any(w == f.stem for w, _ in failures) else 'ok  '} {f.name}")
    return failures


def main() -> None:
    failures = asyncio.run(replay_dir(sys.argv[1] if len(sys.argv) > 1 else "tests/histories"))
    for wid, err in failures:
        print(f"non-deterministic: {wid}: {err}", file=sys.stderr)
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
