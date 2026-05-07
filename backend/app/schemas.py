from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


VideoFormat = Literal["shorts", "long"]


class ProjectCreate(BaseModel):
    idea: str = Field(min_length=5)
    video_format: VideoFormat
    language: str = "english"


class ScriptUpdate(BaseModel):
    video_script: str
    on_screen_notes: str = ""
    title_suggestions: list[str] = []
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
    estimated_duration: str
    tone: str
    approved: bool


class ClipOut(BaseModel):
    id: int
    pexels_id: str
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
    render_status: str
    error_message: str | None


class ProjectOut(BaseModel):
    id: int
    title: str
    idea: str
    video_format: str
    language: str
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
    video_format: str
    language: str
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
