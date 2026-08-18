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
    # session 超时时间（分钟），可通过环境变量 ACCESS_TOKEN_EXPIRE_MINUTES 覆盖
    access_token_expire_minutes: int = 60

    # 管理员账号（密码来自环境变量，不落库；留空则禁用 admin 登录）
    admin_username: str = "admin"
    admin_password: str = ""

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
