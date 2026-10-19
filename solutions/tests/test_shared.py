import pytest
from temporalio.exceptions import ApplicationError
from temporalio.testing import ActivityEnvironment

from solutions.shared import activities, mock_lab


async def test_default_drift_is_detected():
    env = ActivityEnvironment()
    intent = await env.run(activities.get_intent, "bos-acc-01")
    state = await env.run(activities.get_running_config, "bos-acc-01")
    report = await env.run(activities.compute_drift, intent, state)
    assert report.missing_lines == ["ntp server 10.0.0.1"]
    assert not report.version_drift


async def test_version_drift_is_detected():
    env = ActivityEnvironment()
    intent = await env.run(activities.get_intent, "nyc-rtr-01")
    state = await env.run(activities.get_running_config, "nyc-rtr-01")
    report = await env.run(activities.compute_drift, intent, state)
    assert report.version_drift and not report.config_drift


async def test_config_session_commit_timer_and_abort_restores():
    before = mock_lab.config_of("bos-acc-01")
    env = ActivityEnvironment()
    await env.run(activities.stage_config, "bos-acc-01", "s1", ["ntp server 10.0.0.1"])
    assert await env.run(activities.get_session_diff, "bos-acc-01", "s1") == ["+ntp server 10.0.0.1"]
    await env.run(activities.commit_with_timer, "bos-acc-01", "s1", 5)
    assert "ntp server 10.0.0.1" in mock_lab.config_of("bos-acc-01")
    await env.run(activities.abort_session, "bos-acc-01", "s1")
    assert mock_lab.config_of("bos-acc-01") == before


async def test_show_only_guardrail():
    with pytest.raises(ApplicationError) as e:
        await ActivityEnvironment().run(activities.run_show_command, "bos-rtr-01", "configure terminal")
    assert e.value.non_retryable
