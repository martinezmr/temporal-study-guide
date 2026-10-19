"""Minimal Arista eAPI (JSON-RPC over HTTPS) client, async and sync, with a mock switch.

Errors are classified for Temporal:
  * HTTP 401/403 and bad commands -> ApplicationError(non_retryable=True): retrying won't help
  * timeouts, connection errors, 5xx -> normal exceptions: Temporal retries them
"""

import niquests
from temporalio.exceptions import ApplicationError

from solutions.shared import mock_lab, settings


def _payload(commands: list[str], fmt: str) -> dict:
    return {"jsonrpc": "2.0", "method": "runCmds", "id": "temporal",
            "params": {"version": 1, "cmds": commands, "format": fmt}}


def _host(device: str) -> str:
    host = settings.device_hosts().get(device)
    if not host:
        raise ApplicationError(f"no DEVICE_HOSTS entry for {device}", type="UnknownDevice", non_retryable=True)
    return host


def _check(device: str, resp) -> list:
    if resp.status_code in (401, 403):
        raise ApplicationError(f"HTTP {resp.status_code} from {device}: authentication failed",
                               type="AuthError", non_retryable=True)
    resp.raise_for_status()  # 5xx -> retryable
    body = resp.json()
    if "error" in body:
        raise ApplicationError(f"{device}: {body['error'].get('message')}",
                               type="EapiCommandError", non_retryable=True)
    return body["result"]


async def run_commands(device: str, commands: list[str], fmt: str = "json") -> list:
    """Async version: use from `async def` activities."""
    if settings.device_mode() == "mock":
        return mock_lab.run_commands(device, commands, fmt)
    async with niquests.AsyncSession() as s:
        resp = await s.post(f"https://{_host(device)}/command-api", json=_payload(commands, fmt),
                            auth=settings.device_credentials(), verify=False, timeout=30)
    return _check(device, resp)


def run_commands_sync(device: str, commands: list[str], fmt: str = "json") -> list:
    """Blocking version: use from plain `def` activities (run in the worker's thread pool)."""
    if settings.device_mode() == "mock":
        return mock_lab.run_commands(device, commands, fmt)
    with niquests.Session() as s:
        resp = s.post(f"https://{_host(device)}/command-api", json=_payload(commands, fmt),
                      auth=settings.device_credentials(), verify=False, timeout=30)
    return _check(device, resp)
