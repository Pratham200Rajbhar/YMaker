"""
Video rendering service — combines clips, voiceover, and subtitles into a final MP4.

Design:
- Runs as a FastAPI BackgroundTask (separate thread, new DB session).
- SQLite WAL mode is set at engine creation (database.py) to prevent deadlocks.
- MoviePy 2.x imports for video composition.
- Whisper transcription enforced for accurate subtitle generation.
"""

import logging
import textwrap
from pathlib import Path

from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..models import Project, ProjectStatus, Render
from ..storage import ProjectStorage

logger = logging.getLogger(__name__)


class RenderingError(RuntimeError):
    """Raised when video rendering fails."""
    pass


# ---------------------------------------------------------------------------
# SRT utilities
# ---------------------------------------------------------------------------

def _srt_time(seconds: float) -> str:
    ms = int((seconds - int(seconds)) * 1000)
    total = int(seconds)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def _generate_whisper_subtitles(audio_path: str, target: Path) -> None:
    """Generate word-accurate subtitles via Whisper using audio transcription."""
    import whisper
    model = whisper.load_model("base")
    result = model.transcribe(audio_path)
    lines = []
    for idx, segment in enumerate(result.get("segments", []), start=1):
        lines.append(
            f"{idx}\n{_srt_time(segment['start'])} --> {_srt_time(segment['end'])}\n"
            f"{segment['text'].strip()}\n"
        )
    target.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# MoviePy 2.x imports
# ---------------------------------------------------------------------------

def _import_moviepy():
    """Import MoviePy 2.x components."""
    from moviepy import (
        AudioFileClip,
        CompositeVideoClip,
        TextClip,
        VideoFileClip,
        concatenate_videoclips,
    )
    return VideoFileClip, AudioFileClip, CompositeVideoClip, TextClip, concatenate_videoclips


# ---------------------------------------------------------------------------
# Core rendering logic
# ---------------------------------------------------------------------------

def _render_with_moviepy(project: Project, render: Render, db: Session) -> None:
    VideoFileClip, AudioFileClip, CompositeVideoClip, TextClip, concatenate_videoclips = _import_moviepy()

    size = (1080, 1920) if project.video_format == "shorts" else (1920, 1080)
    font_size = 46 if project.video_format == "shorts" else 40
    
    # Common font path for Linux
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    if not Path(font_path).exists():
        # Fallback to just the name if path is missing, though 2.x prefers path
        font_path = "DejaVu-Sans-Bold"

    clips = []
    for scene in project.scenes:
        selected = next(
            (clip for clip in scene.clips if clip.selected and clip.local_path), None
        )
        if not selected:
            raise RenderingError(
                f"Scene {scene.scene_index} has no downloaded selected clip. "
                "Re-approve clips to download them."
            )
        if not Path(selected.local_path).exists():
            raise RenderingError(
                f"Clip file missing on disk: {selected.local_path}. "
                "Re-approve clips to re-download."
            )

        video = VideoFileClip(selected.local_path).without_audio()
        target_duration = min(scene.duration_seconds, video.duration)
        video = video.subclipped(0, target_duration)

        # Scale to fill the target size, then center-crop
        if video.w / video.h < size[0] / size[1]:
            video = video.resized(height=size[1])
        else:
            video = video.resized(width=size[0])
        video = video.cropped(x_center=video.w / 2, y_center=video.h / 2, width=size[0], height=size[1])
        clips.append(video)

    if not clips:
        raise RenderingError("No video clips to render.")

    final = concatenate_videoclips(clips, method="compose")

    # Generate Whisper subtitles from voiceover
    storage = ProjectStorage(project.id)
    subtitle_path = storage.get_subtitle_path()
    _generate_whisper_subtitles(render.voiceover_path, subtitle_path)
    logger.info("Whisper subtitles generated: %s", subtitle_path)
    render.subtitle_path = str(subtitle_path)

    # Audio
    if render.voiceover_path and Path(render.voiceover_path).exists():
        audio = AudioFileClip(render.voiceover_path)
        final = final.with_audio(audio.subclipped(0, min(audio.duration, final.duration)))
    else:
        logger.warning("No voiceover file found at %s — rendering without audio", render.voiceover_path)

    # Caption overlays (burn-in subtitles)
    overlays = [final]
    cursor = 0.0
    wrap_width = 30 if project.video_format == "shorts" else 60
    for scene in sorted(project.scenes, key=lambda s: s.scene_index):
        wrapped = "\n".join(textwrap.wrap(scene.voiceover_text, width=wrap_width)[:2])
        caption = (
            TextClip(
                text=wrapped,
                font=font_path,
                font_size=font_size,
                color="white",
                stroke_color="black",
                stroke_width=2,
            )
            .with_position(("center", size[1] - 240))
            .with_start(cursor)
            .with_duration(scene.duration_seconds)
        )
        overlays.append(caption)
        cursor += scene.duration_seconds

    final = CompositeVideoClip(overlays)

    output = storage.get_render_path()
    # MoviePy 2.x uses threads instead of processes by default, but let's be explicit
    final.write_videofile(str(output), codec="libx264", audio_codec="aac", fps=30, threads=2, logger=None)
    render.render_path = str(output)
    db.flush()
    logger.info("Render complete: %s", output)


# ---------------------------------------------------------------------------
# Background task entry point
# ---------------------------------------------------------------------------

def render_project(project_id: int) -> None:
    """
    Background task — called from the render router via FastAPI BackgroundTasks.
    Opens its own DB session since it runs in a separate thread.
    """
    db = SessionLocal()
    try:
        project = db.get(Project, project_id)
        if not project or not project.render:
            logger.error("render_project called for missing project/render id=%d", project_id)
            return

        render = project.render
        render.render_status = "rendering"
        render.error_message = None
        project.status = ProjectStatus.rendering.value
        db.commit()

        try:
            _render_with_moviepy(project, render, db)
            render.render_status = "complete"
            project.status = ProjectStatus.complete.value
            project.current_stage = "render"
            logger.info("Project %d rendered successfully", project_id)
        except Exception as exc:
            logger.exception("Render failed for project %d", project_id)
            render.render_status = "error"
            render.error_message = str(exc)
            project.status = ProjectStatus.error.value

        db.commit()
    finally:
        db.close()
