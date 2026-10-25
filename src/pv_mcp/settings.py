"""Runtime settings. Secrets stay in the environment or a gitignored .env file."""

from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Process settings for openFDA and the optional HTTP transport.

    `openfda_api_key` is optional. Without it, openFDA applies the anonymous
    rate limit. The key is never written into tool results or the audit log.
    `pv_mcp_token` is required only when the process serves Streamable HTTP.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openfda_base_url: str = "https://api.fda.gov"
    openfda_api_key: SecretStr | None = None
    openfda_timeout_seconds: float = Field(default=20.0, gt=0, le=60)
    label_max_chars: int = Field(default=4000, ge=500, le=20_000)
    openfda_cache_path: Path | None = None
    openfda_cache_ttl_seconds: int = Field(default=3600, ge=1, le=86_400)
    pv_mcp_token: SecretStr | None = None
    pv_mcp_http_host: str = "127.0.0.1"
    pv_mcp_http_port: int = Field(default=8000, ge=1, le=65535)
    pv_mcp_resource_url: str | None = None
    pv_mcp_issuer_url: str = "https://pv-mcp.invalid/dev"
    pv_mcp_rate_limit_per_minute: int = Field(default=60, ge=0, le=10_000)
    pv_mcp_transport: Literal["stdio", "http"] = "stdio"

    @field_validator("openfda_base_url")
    @classmethod
    def strip_base_url(cls, value: str) -> str:
        return value.rstrip("/")

    @field_validator("pv_mcp_http_host")
    @classmethod
    def strip_host(cls, value: str) -> str:
        host = value.strip()
        if not host:
            raise ValueError("PV_MCP_HTTP_HOST must not be empty.")
        return host

    @field_validator("pv_mcp_transport", mode="before")
    @classmethod
    def normalize_transport(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator(
        "openfda_api_key",
        "pv_mcp_token",
        "openfda_cache_path",
        "pv_mcp_resource_url",
        mode="before",
    )
    @classmethod
    def blank_optional(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value
