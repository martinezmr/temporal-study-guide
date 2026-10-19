import asyncio
import time


async def eventually(fetch, predicate=bool, timeout: float = 15.0, interval: float = 0.2):
    """Poll `await fetch()` until predicate(value) is true. Returns the value."""
    deadline = time.monotonic() + timeout
    while True:
        value = await fetch()
        if predicate(value):
            return value
        if time.monotonic() > deadline:
            raise AssertionError(f"condition not met within {timeout}s; last value: {value!r}")
        await asyncio.sleep(interval)
