"""Settings read from the environment at call time (so tests can monkeypatch them).

DEVICE_MODE defaults to "mock" for the solutions, so every demo and test runs without the lab.
Set DEVICE_MODE=live (e.g. via `uv run --env-file .env`) to talk to your cEOS nodes and Nautobot.
"""

import os

COMPLIANCE_NAMESPACE = "compliance"
DEVICE_IO_TASK_QUEUE = "netops-device-io"


def temporal_address() -> str:
    return os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")


def temporal_namespace() -> str:
    return os.environ.get("TEMPORAL_NAMESPACE", "default")


def device_mode() -> str:
    return os.environ.get("DEVICE_MODE", "mock").lower()


def device_credentials() -> tuple[str, str]:
    return os.environ.get("DEVICE_USERNAME", "admin"), os.environ.get("DEVICE_PASSWORD", "admin")


def device_hosts() -> dict[str, str]:
    """Parse DEVICE_HOSTS="bos-rtr-01=172.20.20.2,bos-acc-01=172.20.20.3"."""
    raw = os.environ.get("DEVICE_HOSTS", "")
    pairs = [p.split("=", 1) for p in raw.split(",") if "=" in p]
    return {name.strip(): host.strip() for name, host in pairs}


def nautobot() -> tuple[str, str]:
    return os.environ.get("NAUTOBOT_URL", "http://localhost:8000"), os.environ.get("NAUTOBOT_TOKEN", "")


def anthropic_key() -> str:
    return os.environ.get("ANTHROPIC_API_KEY", "")


def llm_model() -> str:
    return os.environ.get("LLM_MODEL", "claude-sonnet-5-5")
