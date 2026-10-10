from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    database_url: str
    redis_url: str = "redis://localhost:6379/0"
    anthropic_api_key: str = ""
    groq_api_key: str = ""

    # which model answers. ollama locally (free, unlimited), groq in the
    # hosted demo (a 5.2 GB model does not fit a 512 MB container)
    stallo_agent_provider: str = "ollama"
    stallo_agent_model: str = "qwen3:8b"
    stallo_groq_model: str = "openai/gpt-oss-120b"
    ollama_host: str = "http://localhost:11434"
    stallo_env: str = "local"
    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()