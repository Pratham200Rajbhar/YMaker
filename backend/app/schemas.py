from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


VideoFormat = Literal["shorts", "long"]
VideoLength = Literal["auto", "short", "medium", "long"]


class ProjectCreate(BaseModel):
    idea: str = Field(min_length=5)
    category: str = "General"
    video_format: VideoFormat
    video_length: VideoLength = "auto"
    language: str = "english"
    subtitles_enabled: bool = True
    subtitle_language: str = "english"
    # Valid values: "pexels", "pixabay", "coverr", "mixkit", "free", "hybrid"
    clip_provider: str | None = None


class ScriptUpdate(BaseModel):
    video_script: str
    on_screen_notes: str = ""
    title_suggestions: list[str] = []
    description: str | None = None
    tags: list[str] = []
    chapters: list[str] = []
    hook_type: str | None = None
    estimated_duration: str = ""
    tone: str = ""


class SceneUpdate(BaseModel):
    description: str | None = None
    visual_keyword: str | None = None
    duration_seconds: float | None = None
    voiceover_text: str | None = None
    approved: bool | None = None




class ScriptOut(BaseModel):
    id: int
    version: int
    video_script: str
    on_screen_notes: str
    title_suggestions: list[str]
    description: str | None = None
    tags: list[str] = []
    chapters: list[str] = []
    hook_type: str | None = None
    estimated_duration: str
    tone: str
    approved: bool


class ClipOut(BaseModel):
    id: int
    source_id: str
    source: str
    ai_score: float | None = None
    url: str
    preview_url: str | None
    image_url: str | None
    width: int | None
    height: int | None
    duration: float | None
    selected: bool
    local_path: str | None


class SceneOut(BaseModel):
    id: int
    scene_index: int
    description: str
    visual_keyword: str
    duration_seconds: float
    voiceover_text: str
    approved: bool
    clips: list[ClipOut] = []


class RenderOut(BaseModel):
    id: int
    voiceover_path: str | None
    voice_name: str | None
    voiceover_approved: bool
    subtitle_path: str | None
    render_path: str | None
    music_path: str | None = None
    music_name: str | None = None
    render_status: str
    error_message: str | None




class ProjectOut(BaseModel):
    id: int
    title: str
    idea: str
    category: str = "General"
    video_format: str
    video_length: str = "auto"
    language: str
    subtitles_enabled: bool
    subtitle_language: str
    clip_provider: str
    current_stage: str
    status: str
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    latest_script: ScriptOut | None = None
    scenes: list[SceneOut] = []
    render: RenderOut | None = None


class ProjectListItem(BaseModel):
    id: int
    title: str
    category: str = "General"
    video_format: str
    video_length: str = "auto"
    language: str
    subtitles_enabled: bool
    subtitle_language: str
    clip_provider: str
    current_stage: str
    status: str
    created_at: datetime


class IdeaOptimizeRequest(BaseModel):
    idea: str


class IdeaOptimizeResponse(BaseModel):
    optimized_idea: str


class KeywordOptimizeRequest(BaseModel):
    description: str
    keyword: str


class KeywordOptimizeResponse(BaseModel):
    optimized_keyword: str


class VoiceGenerate(BaseModel):
    voice_name: str


class SettingsOut(BaseModel):
    id: int
    llm_provider: str
    ollama_base_url: str
    ollama_model: str
    openai_api_key: str | None = None
    openai_model: str
    openrouter_api_key: str | None = None
    openrouter_model: str
    vertex_project_id: str | None = None
    vertex_location: str
    gemini_model: str
    nvidia_api_key: str | None = None
    nvidia_model: str
    nvidia_tts_model: str
    clip_provider: str
    updated_at: datetime


class SettingsWithLabel(SettingsOut):
    active_provider_label: str


class SettingsUpdate(BaseModel):
    llm_provider: str | None = None
    ollama_base_url: str | None = None
    ollama_model: str | None = None
    openai_api_key: str | None = None
    openai_model: str | None = None
    openrouter_api_key: str | None = None
    openrouter_model: str | None = None
    vertex_project_id: str | None = None
    vertex_location: str | None = None
    gemini_model: str | None = None
    nvidia_api_key: str | None = None
    nvidia_model: str | None = None
    nvidia_tts_model: str | None = None
    clip_provider: str | None = None
