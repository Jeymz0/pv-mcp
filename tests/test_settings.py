"""Environment settings stay free of an empty API key."""

import pytest

from pv_mcp.settings import Settings


def test_blank_api_key_is_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENFDA_API_KEY", "  ")
    settings = Settings(_env_file=None)
    assert settings.openfda_api_key is None
