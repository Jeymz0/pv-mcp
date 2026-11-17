"""Settings for the summary agent. Secrets stay in the environment or .env."""

from pathlib import Path
from typing import Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentSettings(BaseSettings):
    """How the agent reaches the model and the MCP server.

    ``pv_agent_model_provider`` is passed to LangChain's ``init_chat_model``,
    so the same graph can use another chat provider without a code change.
    Groq is the default because the project stays on a free tier.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    groq_api_key: SecretStr | None = None
    pv_agent_model: str = "llama-3.3-70b-versatile"
    pv_agent_model_provider: str = "groq"
    pv_agent_transport: Literal["stdio", "http"] = "stdio"
    pv_agent_mcp_url: str = "http://127.0.0.1:8000/mcp"
    pv_mcp_token: SecretStr | None = None
    pv_agent_reports_dir: Path = Path("reports")
    pv_agent_checkpoint_path: Path = Path(".cache/agent.sqlite")

    @field_validator("pv_agent_model", "pv_agent_model_provider")
    @classmethod
    def require_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Model name and provider must not be empty.")
        return cleaned

    @field_validator("pv_agent_transport", mode="before")
    @classmethod
    def normalize_transport(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("pv_agent_mcp_url")
    @classmethod
    def strip_url(cls, value: str) -> str:
        return value.strip().rstrip("/")

    @field_validator("groq_api_key", "pv_mcp_token", mode="before")
    @classmethod
    def blank_secret(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value
