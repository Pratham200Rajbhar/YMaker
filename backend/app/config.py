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

    # NVIDIA NIM
    nvidia_api_key: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        protected_namespaces=("settings_",),
    )


settings = Settings()


def ensure_storage_dirs() -> None:
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
