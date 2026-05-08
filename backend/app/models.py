from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class VideoFormat(str, Enum):
    shorts = "shorts"
    long = "long"


class WorkflowStage(str, Enum):
    script = "script"
    scenes = "scenes"
    clips = "clips"
    voiceover = "voiceover"
    render = "render"


class ProjectStatus(str, Enum):
    draft = "draft"
    waiting_review = "waiting_review"
    approved = "approved"
    rendering = "rendering"
    complete = "complete"
    error = "error"


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(220), default="Untitled Project")
    idea: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(60), default="General")
    video_format: Mapped[str] = mapped_column(String(20))
    video_length: Mapped[str] = mapped_column(String(20), default="auto")
    language: Mapped[str] = mapped_column(String(20), default="english")
    subtitles_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    subtitle_language: Mapped[str] = mapped_column(String(20), default="english")
    clip_provider: Mapped[str] = mapped_column(String(20), default="hybrid")
    current_stage: Mapped[str] = mapped_column(String(30), default=WorkflowStage.script.value)
    status: Mapped[str] = mapped_column(String(30), default=ProjectStatus.draft.value)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    scripts: Mapped[list["Script"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    scenes: Mapped[list["Scene"]] = relationship(back_populates="project", cascade="all, delete-orphan", order_by="Scene.scene_index")
    render: Mapped["Render | None"] = relationship(back_populates="project", cascade="all, delete-orphan", uselist=False)


class Script(Base):
    __tablename__ = "scripts"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    version: Mapped[int] = mapped_column(Integer, default=1)
    video_script: Mapped[str] = mapped_column(Text, default="")
    on_screen_notes: Mapped[str] = mapped_column(Text, default="")
    title_suggestions: Mapped[str] = mapped_column(Text, default="[]")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[str | None] = mapped_column(Text, nullable=True, default="[]")
    chapters: Mapped[str | None] = mapped_column(Text, nullable=True, default="[]")
    hook_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    estimated_duration: Mapped[str] = mapped_column(String(80), default="")
    tone: Mapped[str] = mapped_column(String(120), default="")
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    project: Mapped[Project] = relationship(back_populates="scripts")


class Scene(Base):
    __tablename__ = "scenes"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    scene_index: Mapped[int] = mapped_column(Integer)
    description: Mapped[str] = mapped_column(Text)
    visual_keyword: Mapped[str] = mapped_column(String(160))
    duration_seconds: Mapped[float] = mapped_column(Float, default=5.0)
    voiceover_text: Mapped[str] = mapped_column(Text, default="")
    approved: Mapped[bool] = mapped_column(Boolean, default=False)

    project: Mapped[Project] = relationship(back_populates="scenes")
    clips: Mapped[list["Clip"]] = relationship(back_populates="scene", cascade="all, delete-orphan")


class Clip(Base):
    __tablename__ = "clips"

    id: Mapped[int] = mapped_column(primary_key=True)
    scene_id: Mapped[int] = mapped_column(ForeignKey("scenes.id"))
    source_id: Mapped[str] = mapped_column(String(80))
    source: Mapped[str] = mapped_column(String(20), default="pexels")
    ai_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    url: Mapped[str] = mapped_column(Text)
    preview_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    name: Mapped[str | None] = mapped_column(Text, nullable=True)
    selected: Mapped[bool] = mapped_column(Boolean, default=False)
    local_path: Mapped[str | None] = mapped_column(Text, nullable=True)

    scene: Mapped[Scene] = relationship(back_populates="clips")


class Render(Base):
    __tablename__ = "renders"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), unique=True)
    voiceover_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    voice_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    voiceover_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    subtitle_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    render_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    music_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    music_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    render_status: Mapped[str] = mapped_column(String(30), default="idle")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project: Mapped[Project] = relationship(back_populates="render")


class Settings(Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    llm_provider: Mapped[str] = mapped_column(String(50), default="ollama")

    # Ollama
    ollama_base_url: Mapped[str] = mapped_column(String(255), default="http://localhost:11434")
    ollama_model: Mapped[str] = mapped_column(String(100), default="llama3")

    # OpenAI
    openai_api_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    openai_model: Mapped[str] = mapped_column(String(100), default="gpt-4o")

    # OpenRouter
    openrouter_api_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    openrouter_model: Mapped[str] = mapped_column(String(100), default="anthropic/claude-3.5-sonnet")

    # Vertex AI
    vertex_project_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    vertex_location: Mapped[str] = mapped_column(String(100), default="us-central1")
    gemini_model: Mapped[str] = mapped_column(String(100), default="gemini-1.5-pro")

    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
