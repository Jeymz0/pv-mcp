"""Environment settings stay free of an empty API key."""

import pytest

from pv_mcp.settings import Settings


def test_blank_api_key_is_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENFDA_API_KEY", "  ")
    settings = Settings(_env_file=None)
    assert settings.openfda_api_key is None


def test_blank_token_and_cache_path_are_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PV_MCP_TOKEN", "  ")
    monkeypatch.setenv("OPENFDA_CACHE_PATH", "  ")
    settings = Settings(_env_file=None)
    assert settings.pv_mcp_token is None
    assert settings.openfda_cache_path is None


def test_explicit_empty_cache_overrides_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENFDA_CACHE_PATH", "/tmp/openfda.sqlite")
    settings = Settings(_env_file=None, openfda_cache_path=None)
    assert settings.openfda_cache_path is None
