"""Runtime settings. Secrets stay in the environment or a gitignored .env file."""

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """openFDA connection settings.

    `openfda_api_key` is optional. Without it, openFDA applies the anonymous
    rate limit. The key is never written into tool results.
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

    @field_validator("openfda_base_url")
    @classmethod
    def strip_base_url(cls, value: str) -> str:
        return value.rstrip("/")

    @field_validator("openfda_api_key", mode="before")
    @classmethod
    def blank_api_key(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value
