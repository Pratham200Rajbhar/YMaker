from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[1]
STORAGE_DIR = BASE_DIR / "storage"


class Settings(BaseSettings):
    app_name: str = "ScriptForge API"
    database_url: str = f"sqlite:///{BASE_DIR / 'scriptforge.db'}"
    frontend_origin: str = "http://localhost:3000"

    # Model Provider: "vertex" or "ollama"
    model_provider: str = "ollama"

    # Vertex AI Config
    vertex_project_id: str | None = None
    vertex_location: str = "us-central1"
    gemini_model: str

    # Ollama Config
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str

    # Pexels
    pexels_api_key: str | None = None

    # Pixabay
    pixabay_api_key: str | None = None

    # Clip Provider: "pexels", "pixabay", or "hybrid"
    clip_provider: str = "hybrid"

    # Background music
    music_enabled: bool = True

    # NVIDIA NIM
    nvidia_api_key: str | None = None

    # FFMPEG
    ffmpeg_binary: str = "ffmpeg"

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        protected_namespaces=("settings_",),
    )


settings = Settings()

# Export FFMPEG_BINARY for MoviePy
import os
os.environ["FFMPEG_BINARY"] = settings.ffmpeg_binary


def ensure_storage_dirs() -> None:
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
