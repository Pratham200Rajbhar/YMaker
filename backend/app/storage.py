import shutil
from pathlib import Path

from .config import STORAGE_DIR


def _validate_path_in_storage(path: Path, storage_base: Path) -> None:
    """Ensure path is within storage directory to prevent path traversal attacks."""
    try:
        path.resolve().relative_to(storage_base.resolve())
    except ValueError:
        raise ValueError(f"Path {path} is outside storage directory {storage_base}")


class ProjectStorage:
    """
    Production-grade file manager ensuring strict project isolation.
    Groups all assets by project_id to avoid collision and allow easy cleanup.
    """

    def __init__(self, project_id: int):
        self.project_id = project_id
        self.base_dir = STORAGE_DIR / f"project_{project_id}"
        
        # Subdirectories for organized assets per project
        self.dirs = {
            "clips": self.base_dir / "clips",
            "voiceovers": self.base_dir / "voiceovers",
            "subtitles": self.base_dir / "subtitles",
            "renders": self.base_dir / "renders",
        }
        self.ensure_dirs()

    def ensure_dirs(self) -> None:
        """Create isolated project directories safely."""
        _validate_path_in_storage(self.base_dir, STORAGE_DIR)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        for path in self.dirs.values():
            _validate_path_in_storage(path, STORAGE_DIR)
            path.mkdir(parents=True, exist_ok=True)

    def get_clip_path(self, clip_id: int, ext: str = ".mp4") -> Path:
        return self.dirs["clips"] / f"clip_{clip_id}{ext}"

    def get_voiceover_path(self, voice_name: str, ext: str = ".mp3") -> Path:
        return self.dirs["voiceovers"] / f"{voice_name}{ext}"

    def get_subtitle_path(self, ext: str = ".srt") -> Path:
        return self.dirs["subtitles"] / f"subtitles{ext}"

    def get_images_dir(self) -> Path:
        images_dir = self.base_dir / "images"
        _validate_path_in_storage(images_dir, STORAGE_DIR)
        images_dir.mkdir(parents=True, exist_ok=True)
        return images_dir

    def get_render_path(self, suffix: str = "", ext: str = ".mp4") -> Path:
        name = f"render{'_' + suffix if suffix else ''}{ext}"
        return self.dirs["renders"] / name

    def clear_project_assets(self) -> None:
        """Completely wipe project files from disk recursively."""
        if self.base_dir.exists():
            shutil.rmtree(self.base_dir)