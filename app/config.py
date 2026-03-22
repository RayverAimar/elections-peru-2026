from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    anthropic_api_key: str
    database_url: str = "postgresql://peru:peru2026@localhost:5434/peru_elecciones"
    data_dir: Path = Path(__file__).resolve().parent.parent / "data"
    cors_origins: list[str] = ["*"]
    chat_rate_limit_rpm: int = 30

    model_config = {"env_file": ".env"}
