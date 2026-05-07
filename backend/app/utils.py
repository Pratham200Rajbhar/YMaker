import json
from pathlib import Path

from .config import STORAGE_DIR
from .models import Clip, Project, Render, Scene, Script
from .schemas import ClipOut, ProjectOut, RenderOut, SceneOut, ScriptOut


def titles_to_json(titles: list[str]) -> str:
    return json.dumps(titles, ensure_ascii=True)


def titles_from_json(raw: str | None) -> list[str]:
    if not raw:
        return []
    value = json.loads(raw)
    if not isinstance(value, list):
        raise ValueError(f"Expected list of titles, got {type(value).__name__}")
    return value


def latest_script(project: Project) -> Script | None:
    return max(project.scripts, key=lambda item: item.version, default=None)


def public_path(path: str | None) -> str | None:
    if not path:
        return None
    try:
        return "/media/" + str(Path(path).resolve().relative_to(STORAGE_DIR.resolve()))
    except ValueError:
        return path


def clip_out(clip: Clip) -> ClipOut:
    return ClipOut(
        id=clip.id,
        pexels_id=clip.pexels_id,
        url=clip.url,
        preview_url=clip.preview_url,
        image_url=clip.image_url,
        width=clip.width,
        height=clip.height,
        duration=clip.duration,
        selected=clip.selected,
        local_path=public_path(clip.local_path),
    )


def script_out(script: Script | None) -> ScriptOut | None:
    if script is None:
        return None
    return ScriptOut(
        id=script.id,
        version=script.version,
        video_script=script.video_script,
        on_screen_notes=script.on_screen_notes,
        title_suggestions=titles_from_json(script.title_suggestions),
        estimated_duration=script.estimated_duration,
        tone=script.tone,
        approved=script.approved,
    )


def scene_out(scene: Scene) -> SceneOut:
    return SceneOut(
        id=scene.id,
        scene_index=scene.scene_index,
        description=scene.description,
        visual_keyword=scene.visual_keyword,
        duration_seconds=scene.duration_seconds,
        voiceover_text=scene.voiceover_text,
        approved=scene.approved,
        clips=[clip_out(clip) for clip in scene.clips],
    )


def render_out(render: Render | None) -> RenderOut | None:
    if render is None:
        return None
    return RenderOut(
        id=render.id,
        voiceover_path=public_path(render.voiceover_path),
        voice_name=render.voice_name,
        voiceover_approved=render.voiceover_approved,
        subtitle_path=public_path(render.subtitle_path),
        render_path=public_path(render.render_path),
        render_status=render.render_status,
        error_message=render.error_message,
    )


def project_out(project: Project) -> ProjectOut:
    return ProjectOut(
        id=project.id,
        title=project.title,
        idea=project.idea,
        video_format=project.video_format,
        language=project.language,
        current_stage=project.current_stage,
        status=project.status,
        error_message=project.error_message,
        created_at=project.created_at,
        updated_at=project.updated_at,
        latest_script=script_out(latest_script(project)),
        scenes=[scene_out(scene) for scene in project.scenes],
        render=render_out(project.render),
    )
