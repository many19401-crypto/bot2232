from functools import lru_cache

from pydantic import Field, PositiveInt, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated runtime configuration. Secrets are read only from environment/.env."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    discord_token: str = Field(min_length=1)
    database_url: str = "postgresql+asyncpg://music:music@localhost:5432/music"
    redis_url: str | None = "redis://localhost:6379/0"
    dev_guild_id: int | None = None
    log_level: str = "INFO"

    default_volume: int = Field(default=65, ge=0, le=100)
    default_max_queue_size: PositiveInt = 100
    default_auto_disconnect_timeout: PositiveInt = 300
    default_autoplay: bool = False
    voice_connect_timeout: PositiveInt = 20
    voice_reconnect_attempts: PositiveInt = 4
    search_rate_limit: PositiveInt = 10
    play_rate_limit: PositiveInt = 20
    playlist_rate_limit: PositiveInt = 5
    max_playlist_tracks: PositiveInt = 500
    search_cache_ttl: PositiveInt = 120
    metadata_cache_ttl: PositiveInt = 900
    ffmpeg_bin: str = "ffmpeg"

    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        level = value.upper()
        if level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("LOG_LEVEL must be DEBUG, INFO, WARNING, ERROR or CRITICAL")
        return level


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
