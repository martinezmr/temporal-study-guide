"""Every activity the solutions use. Workflows import these with imports_passed_through().

All device I/O goes through solutions.shared.eapi, so the same activity works against the mock lab
(DEVICE_MODE=mock, the default) and your cEOS nodes (DEVICE_MODE=live).
"""

import os
import re
from pathlib import Path

from temporalio import activity
from temporalio.exceptions import ApplicationError

from solutions.shared import eapi, mock_lab, nautobot, settings
from solutions.shared.models import BackupReport, DeviceFacts, DeviceIntent, DeviceState, DriftReport

# ---- Week 1: facts, config, inventory -------------------------------------------------------


@activity.defn
async def get_device_facts(device: str) -> DeviceFacts:
    v = (await eapi.run_commands(device, ["show version"]))[0]
    return DeviceFacts(device=device, hostname=v.get("hostname", device), model=v["modelName"], version=v["version"])


@activity.defn
async def get_running_config(device: str) -> DeviceState:
    # Two calls: eAPI's format applies to the whole request, and we want JSON + text.
    version = (await eapi.run_commands(device, ["show version"]))[0]
    running = (await eapi.run_commands(device, ["show running-config"], fmt="text"))[0]
    return DeviceState(device=device, version=version["version"], running_config=running["output"])


@activity.defn
async def list_devices() -> list[str]:
    return await nautobot.list_devices()


@activity.defn
async def get_intent(device: str) -> DeviceIntent:
    return await nautobot.get_intent(device)


@activity.defn
async def save_backups(states: list[DeviceState]) -> list[str]:
    """Idempotent: writing the same file twice gives the same result."""
    out = Path(os.environ.get("BACKUP_DIR", "backups"))
    out.mkdir(parents=True, exist_ok=True)
    for s in states:
        (out / f"{s.device}.cfg").write_text(s.running_config)
    return [s.device for s in states]


@activity.defn
async def compute_drift(intent: DeviceIntent, state: DeviceState) -> DriftReport:
    """Lives in an activity so the diff logic can change without versioning any workflow."""
    running = {line.strip() for line in state.running_config.splitlines()}
    missing = [line for line in intent.config_lines if line.strip() not in running]
    return DriftReport(device=intent.device, missing_lines=missing,
                       running_version=state.version, target_version=intent.target_version)


def build_backup_report(devices: list[str], results: list) -> BackupReport:
    ok = [r.device for r in results if isinstance(r, DeviceState)]
    return BackupReport(saved=ok, failed=[d for d, r in zip(devices, results) if not isinstance(r, DeviceState)])


# ---- Week 1, Day 5: blocking (sync) activities, heartbeats --------------------------------------

SHOW_TECH_COMMANDS = [
    "show tech-support | section ip", "show platform fap", "show processes top once",
    "show tech-support | section interface", "show tech-support | section bgp",
]


@activity.defn
def get_lldp_neighbors(device: str) -> list[dict]:
    """Sync activity: the blocking HTTP call runs in the worker's ThreadPoolExecutor."""
    return eapi.run_commands_sync(device, ["show lldp neighbors"])[0]["lldpNeighbors"]


@activity.defn
def collect_show_tech(device: str) -> list[str]:
    """Long, resumable activity. Heartbeats its progress; a retry resumes from the last heartbeat."""
    details = activity.info().heartbeat_details
    start = int(details[0]) if details else 0
    if start:
        activity.logger.info("Resuming show tech for %s at command %d", device, start)
    output: list[str] = []
    for i, cmd in enumerate(SHOW_TECH_COMMANDS[start:], start=start):
        if activity.is_cancelled():
            activity.logger.info("Cancelled at command %d; cleaning up", i)
            raise ApplicationError("show tech cancelled", type="Cancelled", non_retryable=True)
        output.append(eapi.run_commands_sync(device, [cmd], fmt="text")[0]["output"])
        activity.heartbeat(i + 1)
    return output


# ---- Week 3, Day 17: config sessions (saga steps) ---------------------------------------------


@activity.defn
async def stage_config(device: str, session: str, lines: list[str]) -> None:
    await eapi.run_commands(device, [f"configure session {session}", *lines, "end"])


@activity.defn
async def get_session_diff(device: str, session: str) -> list[str]:
    out = (await eapi.run_commands(device, [f"show session-config named {session} diffs"], fmt="text"))[0]
    return [line for line in out["output"].splitlines() if line.strip()]


@activity.defn
async def commit_with_timer(device: str, session: str, minutes: int) -> None:
    await eapi.run_commands(device, [f"configure session {session}", f"commit timer 00:{minutes:02d}:00"])


@activity.defn
async def confirm_commit(device: str, session: str) -> None:
    await eapi.run_commands(device, [f"configure session {session}", "commit"])


@activity.defn
async def abort_session(device: str, session: str) -> None:
    """Compensation. Safe to run even if nothing was staged."""
    try:
        await eapi.run_commands(device, [f"configure session {session}", "abort"])
    except ApplicationError as e:
        activity.logger.warning("abort_session on %s: %s (ignored)", device, e)


@activity.defn
async def verify_compliance(device: str, required_lines: list[str], force_failure: bool = False) -> bool:
    if force_failure:
        return False
    running = (await eapi.run_commands(device, ["show running-config"], fmt="text"))[0]["output"]
    present = {line.strip() for line in running.splitlines()}
    return all(line.strip() in present for line in required_lines)


# ---- Capstone: upgrade stand-ins (cEOS can't be upgraded in place) ------------------------------


@activity.defn
async def precheck_snapshot(device: str) -> dict:
    lldp = (await eapi.run_commands(device, ["show lldp neighbors"]))[0]["lldpNeighbors"]
    return {"lldp": sorted(f"{n['port']}->{n['neighborDevice']}" for n in lldp)}


@activity.defn
async def check_image(device: str, target_version: str) -> bool:
    activity.logger.info("Pretending %s has EOS-%s.swi in flash:", device, target_version)
    return True


@activity.defn
async def simulate_reload(device: str, target_version: str) -> None:
    """Mock: flips the version. Live: logs only, because cEOS images can't be upgraded in place."""
    if settings.device_mode() == "mock":
        mock_lab.set_version(device, target_version)
    else:
        activity.logger.warning("LIVE MODE: not reloading %s; upgrade is simulated", device)


@activity.defn
async def postcheck_compare(device: str, before: dict) -> list[str]:
    after = await precheck_snapshot(device)
    return sorted(set(before["lldp"]) ^ set(after["lldp"]))


# ---- Week 4: read-only troubleshooting tools ---------------------------------------------------

SHOW_ONLY = re.compile(r"^show\s+[\w\s\-|]+$")


@activity.defn
async def get_interfaces(device: str) -> dict:
    return (await eapi.run_commands(device, ["show interfaces status"]))[0]["interfaceStatuses"]


@activity.defn
async def get_lldp(device: str) -> list[dict]:
    return (await eapi.run_commands(device, ["show lldp neighbors"]))[0]["lldpNeighbors"]


@activity.defn
async def get_bgp_summary(device: str) -> dict:
    return (await eapi.run_commands(device, ["show ip bgp summary"]))[0]


@activity.defn
async def get_logging(device: str) -> str:
    return (await eapi.run_commands(device, ["show logging"], fmt="text"))[0]["output"]


@activity.defn
async def run_show_command(device: str, command: str) -> str:
    """Guardrail (Day 28): only `show ...` commands, ever. Anything else fails without retrying."""
    if not SHOW_ONLY.match(command.strip()):
        raise ApplicationError(f"blocked non-show command: {command!r}", type="CommandNotAllowed",
                               non_retryable=True)
    out = (await eapi.run_commands(device, [command.strip()], fmt="text"))[0]
    return out.get("output", str(out))


DEVICE_ACTIVITIES = [
    get_device_facts, get_running_config, list_devices, get_intent, save_backups, compute_drift,
    get_lldp_neighbors, collect_show_tech, stage_config, get_session_diff, commit_with_timer,
    confirm_commit, abort_session, verify_compliance, precheck_snapshot, check_image, simulate_reload,
    postcheck_compare, get_interfaces, get_lldp, get_bgp_summary, get_logging, run_show_command,
]
