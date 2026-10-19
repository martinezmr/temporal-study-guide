"""Pydantic models used across days. Used with temporalio.contrib.pydantic.pydantic_data_converter."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class DeviceFacts(BaseModel):
    device: str
    hostname: str
    model: str
    version: str


class DeviceIntent(BaseModel):
    device: str
    role: str
    site: str
    target_version: str
    config_lines: list[str] = []


class DeviceState(BaseModel):
    device: str
    version: str
    running_config: str


class DriftReport(BaseModel):
    device: str
    missing_lines: list[str] = []
    running_version: str = ""
    target_version: str = ""

    @property
    def version_drift(self) -> bool:
        return bool(self.target_version) and self.running_version != self.target_version

    @property
    def config_drift(self) -> bool:
        return bool(self.missing_lines)

    @property
    def drifted(self) -> bool:
        return self.config_drift or self.version_drift


class BackupReport(BaseModel):
    saved: list[str] = []
    failed: list[str] = []


class DriftExplanation(BaseModel):
    device: str
    summary: str
    risk: Literal["low", "medium", "high"]
    likely_cause: str


class ComplianceInput(BaseModel):
    device: str
    missing_lines: list[str]
    commit_timer_minutes: int = 5
    # Demo/test knob: make verification fail so you can watch the saga roll back.
    force_verify_failure: bool = False


class ComplianceResult(BaseModel):
    device: str
    applied: bool
    diff: list[str] = []
    detail: str = ""


class UpgradeInput(BaseModel):
    device: str
    target_version: str
    tz_offset_hours: int = -5
    skip_window: bool = False


class UpgradeResult(BaseModel):
    device: str
    upgraded: bool
    from_version: str = ""
    to_version: str = ""
    detail: str = ""


class StatusStamp(BaseModel):
    at: datetime
    note: str = ""
