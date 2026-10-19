"""Tool registry: name -> (activity, argument names, description). Every tool is a Temporal activity."""

from solutions.shared import mock_lab
from solutions.shared.activities import get_bgp_summary, get_interfaces, get_lldp, get_logging, run_show_command

DEVICES = sorted(mock_lab.TOPOLOGY)

TOOLS = {
    "get_interfaces": (get_interfaces, ["device"], "Interface link status and descriptions for one device."),
    "get_lldp": (get_lldp, ["device"], "LLDP neighbors (local port, neighbor device, neighbor port) for one device."),
    "get_bgp_summary": (get_bgp_summary, ["device"], "BGP peer summary for one device."),
    "get_logging": (get_logging, ["device"], "Recent syslog messages from one device."),
    "run_show_command": (run_show_command, ["device", "command"],
                         "Run one read-only EOS 'show ...' command. Anything else is rejected."),
}


def tool_spec(name: str) -> dict:
    _, args, description = TOOLS[name]
    props: dict = {"device": {"type": "string", "enum": DEVICES}}
    if "command" in args:
        props["command"] = {"type": "string", "description": "e.g. 'show ip route'"}
    return {"name": name, "description": description,
            "input_schema": {"type": "object", "properties": props, "required": args}}
