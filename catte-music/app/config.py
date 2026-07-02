"""配置管理：从环境变量读取所有配置。"""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # 数据库
    database_url: str = "sqlite+aiosqlite:///./dev.db"

    # JWT
    secret_key: str = "change-me-to-a-random-secret"
    algorithm: str = "HS256"
    access_token_expire_days: int = 7

    # Apple Music
    apple_music_key_id: str = ""
    apple_music_team_id: str = ""
    apple_music_private_key_path: str = ""
    apple_music_developer_token: str = ""

    # 爬虫
    crawl_delay_min: float = 2.0
    crawl_delay_max: float = 5.0

    # CORS
    frontend_origin: str = "http://localhost:5173"

    @property
    def project_root(self) -> Path:
        return Path(__file__).resolve().parent.parent


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
