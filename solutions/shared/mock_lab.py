"""An in-memory stand-in for your 4 cEOS nodes and Nautobot.

It answers the eAPI commands the solutions use, keeps per-device running config, supports
Arista-style config sessions (stage / diff / commit timer / commit / abort), and lets demos and
tests inject failures and drift. State is per-process; call reset() between tests.

Default drift (so the orchestrator has something to find):
  * bos-acc-01 is missing "ntp server 10.0.0.1"
  * nyc-rtr-01 runs 4.31.2F but intent says 4.32.0F
"""

from __future__ import annotations

import copy
import re
import threading
import time

from temporalio.exceptions import ApplicationError

TARGET_VERSION = "4.32.0F"
REQUIRED_LINES = ["ntp server 10.0.0.1", "logging host 10.0.0.50", "aaa authorization exec default local"]

TOPOLOGY = {  # local port -> (neighbor, neighbor port); matches lab/ceos-clab.clab.yml
    "bos-acc-01": {"Ethernet1": ("bos-rtr-01", "Ethernet1"), "Ethernet2": ("nyc-rtr-01", "Ethernet2")},
    "bos-rtr-01": {"Ethernet1": ("bos-acc-01", "Ethernet1"), "Ethernet2": ("nyc-acc-01", "Ethernet2")},
    "nyc-acc-01": {"Ethernet1": ("nyc-rtr-01", "Ethernet1"), "Ethernet2": ("bos-rtr-01", "Ethernet2")},
    "nyc-rtr-01": {"Ethernet1": ("nyc-acc-01", "Ethernet1"), "Ethernet2": ("bos-acc-01", "Ethernet2")},
}

INTENT = {
    "bos-acc-01": {"role": "access", "site": "bos"},
    "bos-rtr-01": {"role": "router", "site": "bos"},
    "nyc-acc-01": {"role": "access", "site": "nyc"},
    "nyc-rtr-01": {"role": "router", "site": "nyc"},
}

# Slow-command delay for collect_show_tech demos (seconds). Tests set this to 0.
SHOW_TECH_DELAY = 1.0

_lock = threading.RLock()
_state: dict[str, dict] = {}
_failures: dict[str, list[str]] = {}
calls: list[tuple[str, list[str]]] = []  # every (device, commands) call, for assertions


def _base_config(device: str) -> list[str]:
    lines = [f"hostname {device}", *REQUIRED_LINES]
    for port, (nbr, _) in TOPOLOGY[device].items():
        lines += [f"interface {port}", f"   description to-{nbr}", "   no switchport"]
    return lines


def reset() -> None:
    with _lock:
        _state.clear()
        _failures.clear()
        calls.clear()
        for device in TOPOLOGY:
            _state[device] = {
                "version": TARGET_VERSION,
                "config": _base_config(device),
                "shutdown": set(),
                "sessions": {},  # name -> list of lines
                "pending": None,  # (session, snapshot) while a commit timer runs
                "log": [f"%SYS-5-CONFIG_I: Configured from console by admin on {device}"],
            }
        _state["bos-acc-01"]["config"].remove("ntp server 10.0.0.1")
        _state["nyc-rtr-01"]["version"] = "4.31.2F"


# ---- helpers for demos and tests ------------------------------------------------------------

def make_compliant() -> None:
    """Remove the default drift."""
    with _lock:
        for device, s in _state.items():
            s["version"] = TARGET_VERSION
            s["config"] = _base_config(device)


def remove_line(device: str, line: str) -> None:
    with _lock:
        if line in _state[device]["config"]:
            _state[device]["config"].remove(line)


def add_line(device: str, line: str) -> None:
    with _lock:
        _state[device]["config"].append(line)


def shutdown_interface(device: str, port: str) -> None:
    with _lock:
        _state[device]["shutdown"].add(port)
        _state[device]["log"].append(f"%LINEPROTO-5-UPDOWN: Line protocol on Interface {port}, changed state to down")


def set_version(device: str, version: str) -> None:
    with _lock:
        _state[device]["version"] = version


def config_of(device: str) -> list[str]:
    with _lock:
        return list(_state[device]["config"])


def fail_next(device: str, times: int = 1, kind: str = "timeout") -> None:
    """kind: "timeout" (retryable) or "auth" (non-retryable)."""
    with _lock:
        _failures.setdefault(device, []).extend([kind] * times)


def attempts(device: str) -> int:
    return sum(1 for d, _ in calls if d == device)


# ---- the fake eAPI --------------------------------------------------------------------------

def run_commands(device: str, commands: list[str], fmt: str = "json") -> list:
    with _lock:
        if not _state:
            reset()
        calls.append((device, list(commands)))
        if device not in _state:
            raise ApplicationError(f"unknown device {device}", type="UnknownDevice", non_retryable=True)
        queue = _failures.get(device)
        if queue:
            kind = queue.pop(0)
            if kind == "auth":
                raise ApplicationError("HTTP 401: authentication failed", type="AuthError", non_retryable=True)
            raise RuntimeError(f"simulated timeout talking to {device}")
        s = _state[device]
        out: list = []
        session: str | None = None
        for cmd in commands:
            c = cmd.strip()
            if c in ("enable", "configure", "configure terminal"):
                out.append({})
            elif c == "show version":
                out.append({"modelName": "cEOSLab", "version": s["version"], "hostname": device})
            elif c == "show running-config":
                text = "\n".join(s["config"])
                out.append({"output": text} if fmt == "text" else {"cmds": {line: None for line in s["config"]}})
            elif c == "show interfaces status":
                out.append({"interfaceStatuses": {
                    p: {"linkStatus": "disabled" if p in s["shutdown"] else "connected", "description": f"to-{n}"}
                    for p, (n, _) in TOPOLOGY[device].items()}})
            elif c == "show lldp neighbors":
                out.append({"lldpNeighbors": [
                    {"port": p, "neighborDevice": n, "neighborPort": np_}
                    for p, (n, np_) in TOPOLOGY[device].items()
                    if p not in s["shutdown"] and p not in _state[n]["shutdown"]]})
            elif c == "show ip bgp summary":
                out.append({"vrfs": {"default": {"peers": {}}}})
            elif c == "show logging":
                out.append({"output": "\n".join(s["log"])})
            elif c.startswith("show tech-support") or c.startswith("show platform") or c.startswith("show processes"):
                time.sleep(SHOW_TECH_DELAY)
                out.append({"output": f"{c} output for {device}"})
            elif m := re.fullmatch(r"configure session (\S+)", c):
                session = m.group(1)
                s["sessions"].setdefault(session, [])
                out.append({})
            elif m := re.fullmatch(r"show session-config named (\S+) diffs", c):
                staged = s["sessions"].get(m.group(1), [])
                out.append({"output": "\n".join(f"+{line}" for line in staged if line not in s["config"])})
            elif c == "end":
                session = None
                out.append({})
            elif session and (m := re.fullmatch(r"commit timer (\d\d:\d\d:\d\d)", c)):
                snapshot = list(s["config"])
                s["config"] += [line for line in s["sessions"].get(session, []) if line not in s["config"]]
                s["pending"] = (session, snapshot)
                s["log"].append(f"%SESSION-5-COMMIT_TIMER: session {session} committed with timer {m.group(1)}")
                out.append({})
            elif session and c == "commit":
                if s["pending"] and s["pending"][0] == session:
                    s["pending"] = None  # confirm a timed commit
                else:
                    s["config"] += [line for line in s["sessions"].get(session, []) if line not in s["config"]]
                s["sessions"].pop(session, None)
                out.append({})
            elif session and c == "abort":
                if s["pending"] and s["pending"][0] == session:
                    s["config"] = s["pending"][1]
                    s["pending"] = None
                s["sessions"].pop(session, None)
                session = None
                out.append({})
            elif session:
                s["sessions"][session].append(c)
                out.append({})
            else:
                raise ApplicationError(f"mock lab does not support command: {c!r}",
                                       type="EapiCommandError", non_retryable=True)
        return copy.deepcopy(out)


reset()
