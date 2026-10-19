import dataclasses

from temporalio.testing import ActivityEnvironment

from solutions.shared.activities import SHOW_TECH_COMMANDS, collect_show_tech


def test_show_tech_heartbeats_each_command():
    env = ActivityEnvironment()
    beats: list = []
    env.on_heartbeat = lambda *details: beats.append(details[0])
    out = env.run(collect_show_tech, "bos-rtr-01")
    assert len(out) == len(SHOW_TECH_COMMANDS)
    assert beats == list(range(1, len(SHOW_TECH_COMMANDS) + 1))


def test_show_tech_resumes_from_heartbeat_details():
    env = ActivityEnvironment()
    env.info = dataclasses.replace(env.info, heartbeat_details=[3])
    out = env.run(collect_show_tech, "bos-rtr-01")
    assert len(out) == len(SHOW_TECH_COMMANDS) - 3
