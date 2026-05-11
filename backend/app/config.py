import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[1]
STORAGE_DIR = BASE_DIR / "storage"
LOGS_DIR = STORAGE_DIR / "logs"
LOG_FILE = LOGS_DIR / "app.jsonl"


class Settings(BaseSettings):
    app_name: str = "MakeVideo API"
    database_url: str = f"sqlite:///{BASE_DIR / 'makevideo.db'}"
    frontend_origin: str = "http://localhost:3000"

    # Pexels
    pexels_api_key: str | None = None

    # Pixabay
    pixabay_api_key: str | None = None

    # Clip Provider options:
    # "pexels"   — Pexels only (requires PEXELS_API_KEY)
    # "pixabay"  — Pixabay only (requires PIXABAY_API_KEY)
    # "coverr"   — Coverr.co only (FREE, no key)
    # "mixkit"   — Mixkit only (FREE, no key)
    # "free"     — Coverr + Mixkit only (fully free, no keys needed)
    # "hybrid"   — All sources combined (best results, keys optional)
    clip_provider: str = "hybrid"

    # Background music
    music_enabled: bool = True

    # NVIDIA NIM
    nvidia_api_key: str | None = None
    nvidia_model: str = "meta/llama-3.1-405b-instruct"
    nvidia_tts_model: str = "877104f7-e885-42b9-8de8-f6e4c6303969"

    # LLM Provider Selection
    # Options: ollama, openai, openrouter, vertex, nvidia
    llm_provider: str = "ollama"

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3"

    # OpenAI
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o"

    # OpenRouter
    openrouter_api_key: str | None = None
    openrouter_model: str = "anthropic/claude-3.5-sonnet"

    # Vertex AI (Gemini)
    vertex_project_id: str | None = None
    vertex_location: str = "us-central1"
    gemini_model: str = "gemini-1.5-pro"

    # FFMPEG
    ffmpeg_binary: str = "ffmpeg"

    model_config = SettingsConfigDict(
        env_file=(BASE_DIR / ".env", BASE_DIR / ".env.local"),
        env_file_encoding="utf-8",
        protected_namespaces=("settings_",),
        extra="ignore",
    )

    def model_post_init(self, __context):
        """Validate settings after initialization."""
        valid_providers = {"pexels", "pixabay", "coverr", "mixkit", "free", "hybrid"}
        provider = (self.clip_provider or "hybrid").lower()
        if provider not in valid_providers:
            raise ValueError(
                f"Invalid clip_provider: {provider!r}. "
                f"Must be one of: {', '.join(sorted(valid_providers))}"
            )


settings = Settings()

# Export FFMPEG_BINARY for MoviePy
os.environ["FFMPEG_BINARY"] = settings.ffmpeg_binary


def ensure_storage_dirs() -> None:
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
