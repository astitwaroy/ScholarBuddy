from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://dev:dev@localhost:5432/schemes"

    # Language model. "gemini" (free tier available), "openai" (any OpenAI-compatible API, e.g. Groq),
    # or "none" (answers are built from the retrieved passages without a model).
    llm_provider: str = "gemini"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.5-flash-lite"
    gemini_fallback_model: str = "gemini-3.8-flash"
    embed_model: str = "gemini-embedding-001"
    openai_base_url: str = "https://api.groq.com/openai/v1"
    openai_api_key: str | None = None
    openai_model: str = "llama-3.3-70b-versatile"

    # Download, parse and index the official documents in the background on startup.
    auto_ingest: bool = True
    # Protects /api/admin/* (re-ingest, evaluation). Leave empty to disable those routes.
    admin_token: str | None = None

    data_dir: Path = ROOT / "data"
    web_dist: Path = ROOT / "web" / "dist"

    @property
    def llm_enabled(self) -> bool:
        if self.llm_provider == "gemini":
            return bool(self.gemini_api_key)
        if self.llm_provider == "openai":
            return bool(self.openai_api_key)
        return False

    @property
    def embeddings_enabled(self) -> bool:
        return bool(self.gemini_api_key)


EMBED_DIM = 768


@lru_cache
def settings() -> Settings:
    return Settings()
