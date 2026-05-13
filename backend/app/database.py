import logging
from collections.abc import Generator

from sqlalchemy import event, text
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings

logger = logging.getLogger(__name__)


engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
)


@event.listens_for(engine, "connect")
def _set_sqlite_wal(dbapi_connection, connection_record):
    """
    Enable SQLite WAL (Write-Ahead Logging) mode on every new connection.

    WAL allows concurrent readers and one writer without deadlocking, which is
    essential because the background render task opens its own session while the
    FastAPI request threads are also reading.
    """
    if settings.database_url.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    # Simple migration for new columns - only run if columns don't exist
    if settings.database_url.startswith("sqlite"):
        with engine.connect() as conn:
            # Check for category column in projects
            res = conn.execute(text("PRAGMA table_info(projects)"))
            columns = [row[1] for row in res.fetchall()]
            if "category" not in columns:
                conn.execute(text("ALTER TABLE projects ADD COLUMN category TEXT NOT NULL DEFAULT 'General'"))
                conn.commit()
            if "video_length" not in columns:
                conn.execute(text("ALTER TABLE projects ADD COLUMN video_length TEXT NOT NULL DEFAULT 'auto'"))
                conn.commit()

            # Check for NVIDIA columns in settings
            res = conn.execute(text("PRAGMA table_info(settings)"))
            setting_columns = [row[1] for row in res.fetchall()]
            if "nvidia_api_key" not in setting_columns:
                conn.execute(text("ALTER TABLE settings ADD COLUMN nvidia_api_key TEXT"))
                conn.commit()
            if "nvidia_model" not in setting_columns:
                conn.execute(text("ALTER TABLE settings ADD COLUMN nvidia_model TEXT NOT NULL DEFAULT ''"))
                conn.commit()
            if "nvidia_tts_model" not in setting_columns:
                conn.execute(text("ALTER TABLE settings ADD COLUMN nvidia_tts_model TEXT NOT NULL DEFAULT '877104f7-e885-42b9-8de8-f6e4c6303969'"))
                conn.commit()

            # Create indexes for better query performance
            try:
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_projects_created_at ON projects(created_at DESC)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_scenes_project_id ON scenes(project_id)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_clips_scene_id ON clips(scene_id)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_scripts_project_id ON scripts(project_id)"))
                conn.commit()
            except Exception as e:
                # Index creation may fail if they already exist with different definitions
                logging.getLogger(__name__).warning("Index creation failed (may already exist): %s", e)
