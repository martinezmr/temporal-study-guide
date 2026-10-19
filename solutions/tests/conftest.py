import pytest

from solutions.shared import mock_lab


@pytest.fixture(autouse=True)
def fresh_mock_lab(monkeypatch, tmp_path):
    """Every test starts with the default mock lab and mock mode, and writes backups to tmp."""
    monkeypatch.setenv("DEVICE_MODE", "mock")
    monkeypatch.setenv("BACKUP_DIR", str(tmp_path / "backups"))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    mock_lab.SHOW_TECH_DELAY = 0
    mock_lab.reset()
    yield
