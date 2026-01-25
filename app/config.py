from pydantic_settings import BaseSettings
from typing import List
import secrets


class Settings(BaseSettings):
    # 数据库配置
    DATABASE_URL: str = "postgresql://wordmaster:password@localhost:5432/postgres"

    # JWT配置
    SECRET_KEY: str = secrets.token_urlsafe(32)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # 大模型配置
    DEFAULT_LLM_API_KEY: str = ""
    DEFAULT_LLM_BASE_URL: str = "https://api.openai.com/v1"
    DEFAULT_LLM_MODEL: str = "gpt-4"

    # 服务器配置
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = True

    # CORS配置
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:19006,http://localhost:3000"

    # TTS配置
    TTS_VOICE: str = "en-US-AriaNeural"
    TTS_RATE: str = "+0%"
    TTS_CACHE_DIR: str = "./tts_cache"

    # Development Token (Skip auth for testing)
    DEV_TOKEN: str = ""

    class Config:
        env_file = ".env"
        case_sensitive = False

    @property
    def allowed_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",")]


settings = Settings()