"""
Video rendering service — combines clips, voiceover, and subtitles into a final MP4.

Design:
- Runs as a FastAPI BackgroundTask (separate thread, new DB session).
- SQLite WAL mode is set at engine creation (database.py) to prevent deadlocks.
- MoviePy 2.x imports for video composition.
- Whisper transcription enforced for accurate subtitle generation.
"""

import logging
import math
import random
from pathlib import Path

from sqlalchemy.orm import Session

from ..config import STORAGE_DIR, settings
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


def _generate_whisper_subtitles(audio_path: str, target: Path, language: str = "english") -> list[dict]:
    """Generate subtitles and return per-word timings for karaoke captions."""
    import whisper
    model = whisper.load_model("base", device="cuda")
    language_code = {"hindi": "hi", "english": "en"}.get(language.lower(), language)
    result = model.transcribe(audio_path, word_timestamps=True, language=language_code)
    lines = []
    words = []
    for idx, segment in enumerate(result.get("segments", []), start=1):
        lines.append(
            f"{idx}\n{_srt_time(segment['start'])} --> {_srt_time(segment['end'])}\n"
            f"{segment['text'].strip()}\n"
        )
        for word in segment.get("words", []):
            text = str(word.get("word", "")).strip()
            if not text:
                continue
            words.append(
                {
                    "text": text,
                    "start": float(word.get("start", segment["start"])),
                    "end": float(word.get("end", segment["end"])),
                }
            )
    target.write_text("\n".join(lines), encoding="utf-8")
    return words


def _normalize_audio_loudness(audio_path: str, target_lufs: float = -14.0) -> None:
    """Normalize audio to target LUFS when pyloudnorm is available."""
    try:
        import pyloudnorm as pyln
        import soundfile as sf

        data, rate = sf.read(audio_path)
        meter = pyln.Meter(rate)
        loudness = meter.integrated_loudness(data)
        normalized = pyln.normalize.loudness(data, loudness, target_lufs)
        sf.write(audio_path, normalized, rate)
    except Exception as exc:
        logger.warning("Audio loudness normalization skipped for %s: %s", audio_path, exc)


def _load_background_music(music_name: str | None = None) -> str | None:
    """Load a requested or random music file from backend/storage/music."""
    if not settings.music_enabled:
        return None

    music_dir = STORAGE_DIR / "music"
    if not music_dir.exists() or not music_dir.is_dir():
        return None

    if music_name:
        requested = (music_dir / music_name).resolve()
        try:
            requested.relative_to(music_dir.resolve())
        except ValueError:
            requested = music_dir / Path(music_name).name
        if requested.exists() and requested.suffix.lower() in {".mp3", ".wav"}:
            return str(requested)

    candidates = [path for path in music_dir.iterdir() if path.suffix.lower() in {".mp3", ".wav"}]
    if not candidates:
        return None
    return str(random.choice(candidates))


# ---------------------------------------------------------------------------
# MoviePy 2.x imports
# ---------------------------------------------------------------------------

def _import_moviepy():
    """Import MoviePy 2.x components."""
    from moviepy import (
        AudioFileClip,
        CompositeAudioClip,
        CompositeVideoClip,
        TextClip,
        VideoFileClip,
        concatenate_videoclips,
    )
    return VideoFileClip, AudioFileClip, CompositeAudioClip, CompositeVideoClip, TextClip, concatenate_videoclips


def _resolve_caption_font(project: Project) -> str:
    """Pick a font that can actually render the selected language."""
    language = f"{project.language} {project.subtitle_language}".lower()
    if "hindi" in language or "hi" in language:
        for path in (
            "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Bold.ttf",
            "/usr/share/fonts/truetype/noto/NotoSansDevanagari-SemiBold.ttf",
            "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",
        ):
            if Path(path).exists():
                return path

    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    ):
        if Path(path).exists():
            return path
    return "DejaVu-Sans-Bold"


def _loop_audio_to_duration(audio, duration: float):
    if audio.duration >= duration:
        return audio.subclipped(0, duration)
    try:
        from moviepy import afx

        return audio.with_effects([afx.AudioLoop(duration=duration)])
    except Exception:
        from moviepy import concatenate_audioclips

        loops = int(duration // audio.duration) + 1
        return concatenate_audioclips([audio] * loops).subclipped(0, duration)


def _fit_video_duration(video, duration: float, concatenate_videoclips):
    """Make the visual track exactly match the master audio duration."""
    if duration <= 0:
        return video
    if video.duration >= duration:
        return video.subclipped(0, duration)
    loops = max(1, math.ceil(duration / max(video.duration, 0.01)))
    return concatenate_videoclips([video] * loops, method="compose").subclipped(0, duration)


# ---------------------------------------------------------------------------
# Core rendering logic
# ---------------------------------------------------------------------------

def _render_with_moviepy(project: Project, render: Render, db: Session) -> None:
    VideoFileClip, AudioFileClip, CompositeAudioClip, CompositeVideoClip, TextClip, concatenate_videoclips = _import_moviepy()

    size = (1080, 1920) if project.video_format == "shorts" else (1920, 1080)
    font_size = 64 if project.video_format == "shorts" else 52
    font_path = _resolve_caption_font(project)
    storage = ProjectStorage(project.id)

    if not render.voiceover_path or not Path(render.voiceover_path).exists():
        raise RenderingError(f"Voiceover file missing on disk: {render.voiceover_path}")

    _normalize_audio_loudness(render.voiceover_path)
    voiceover_source = AudioFileClip(render.voiceover_path)
    master_duration = max(0.01, float(voiceover_source.duration))

    clips = []
    for scene in sorted(project.scenes, key=lambda item: item.scene_index):
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
        target_duration = min(max(scene.duration_seconds, 0.1), video.duration)
        video = video.subclipped(0, target_duration)

        # Scale to fill the target size, then center-crop
        if video.w / video.h < size[0] / size[1]:
            video = video.resized(height=size[1])
        else:
            video = video.resized(width=size[0])
        video = video.cropped(x_center=video.w / 2, y_center=video.h / 2, width=size[0], height=size[1])
        if clips:
            try:
                from moviepy import vfx

                video = video.with_effects([vfx.CrossFadeIn(0.25)])
            except Exception:
                logger.warning("Crossfade transition skipped for scene %d", scene.scene_index)
        clips.append(video)

    if not clips:
        raise RenderingError("No video clips to render.")

    final = concatenate_videoclips(clips, method="compose", padding=-0.25 if len(clips) > 1 else 0)
    final = _fit_video_duration(final, master_duration, concatenate_videoclips)

    # Generate Whisper subtitles from voiceover
    word_timings = []
    if project.subtitles_enabled:
        subtitle_path = storage.get_subtitle_path()
        word_timings = _generate_whisper_subtitles(render.voiceover_path, subtitle_path, language=project.subtitle_language)
        logger.info("Whisper subtitles generated: %s (language: %s)", subtitle_path, project.subtitle_language)
        render.subtitle_path = str(subtitle_path)
    else:
        logger.info("Subtitles disabled for project %d", project.id)
        render.subtitle_path = None

    voiceover = voiceover_source.subclipped(0, final.duration)
    music_path = _load_background_music(render.music_name)
    if music_path:
        render.music_path = music_path
        if not render.music_name:
            render.music_name = Path(music_path).name
        music = _loop_audio_to_duration(AudioFileClip(music_path), final.duration).with_volume_scaled(0.10)
        final = final.with_audio(CompositeAudioClip([voiceover, music]))
    else:
        render.music_path = None
        final = final.with_audio(voiceover)

    # Karaoke caption overlays
    overlays = [final]
    caption_y = int(size[1] * (0.55 if project.video_format == "shorts" else 0.85))
    for word in word_timings:
        duration = max(0.01, float(word["end"]) - float(word["start"]))
        caption = (
            TextClip(
                text=word["text"],
                font=font_path,
                font_size=font_size,
                color="white",
                stroke_color="black",
                stroke_width=3,
            )
            .with_position(("center", caption_y))
            .with_start(float(word["start"]))
            .with_duration(duration)
        )
        overlays.append(caption)

    final = CompositeVideoClip(overlays)

    output = storage.get_render_path()
    fps = 30 if project.video_format == "shorts" else 60

    try:
        logger.info("Starting render with GPU acceleration (h264_nvenc)...")
        final.write_videofile(
            str(output),
            fps=fps,
            codec="h264_nvenc",
            audio_codec="aac",
            preset="p4",  # NVENC uses different presets (p1-p7), 'p4' is medium
            threads=4,
            logger=None,
        )
    except Exception as exc:
        logger.warning("GPU render failed, falling back to CPU (libx264). Error: %s", exc)
        final.write_videofile(
            str(output),
            fps=fps,
            codec="libx264",
            audio_codec="aac",
            preset="superfast",
            threads=4,
            logger=None,
        )
    
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
