"""Intent from Nautobot (GraphQL), or from the mock lab.

Live mode expects each device to have a config context like:
    {"target_version": "4.32.0F", "required_lines": ["ntp server 10.0.0.1", "logging host 10.0.0.50"]}
"""

import niquests
from temporalio.exceptions import ApplicationError

from solutions.shared import mock_lab, settings
from solutions.shared.models import DeviceIntent

DEVICES_QUERY = "query { devices { name } }"
INTENT_QUERY = """
query ($name: [String]) {
  devices(name: $name) { name role { name } location { name } config_context }
}
"""


async def _graphql(query: str, variables: dict | None = None) -> dict:
    url, token = settings.nautobot()
    async with niquests.AsyncSession() as s:
        resp = await s.post(f"{url}/api/graphql/", json={"query": query, "variables": variables or {}},
                            headers={"Authorization": f"Token {token}"}, timeout=30)
    if resp.status_code in (401, 403):
        raise ApplicationError("Nautobot rejected the token", type="AuthError", non_retryable=True)
    resp.raise_for_status()
    body = resp.json()
    if body.get("errors"):
        raise ApplicationError(str(body["errors"]), type="GraphQLError", non_retryable=True)
    return body["data"]


async def list_devices() -> list[str]:
    if settings.device_mode() == "mock":
        return sorted(mock_lab.INTENT)
    data = await _graphql(DEVICES_QUERY)
    return sorted(d["name"] for d in data["devices"])


async def get_intent(device: str) -> DeviceIntent:
    if settings.device_mode() == "mock":
        meta = mock_lab.INTENT[device]
        return DeviceIntent(device=device, role=meta["role"], site=meta["site"],
                            target_version=mock_lab.TARGET_VERSION,
                            config_lines=[f"hostname {device}", *mock_lab.REQUIRED_LINES])
    data = await _graphql(INTENT_QUERY, {"name": [device]})
    if not data["devices"]:
        raise ApplicationError(f"{device} not in Nautobot", type="UnknownDevice", non_retryable=True)
    d = data["devices"][0]
    ctx = d.get("config_context") or {}
    return DeviceIntent(device=device, role=(d.get("role") or {}).get("name", ""),
                        site=(d.get("location") or {}).get("name", ""),
                        target_version=ctx.get("target_version", ""),
                        config_lines=[f"hostname {device}", *ctx.get("required_lines", [])])
