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
import shutil
import subprocess
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from ..config import STORAGE_DIR, settings
from ..database import SessionLocal
from ..models import Project, ProjectStatus, Render
from ..storage import ProjectStorage

logger = logging.getLogger(__name__)

IMAGE_STORY_RESOLUTION = (1920, 1080)


# Module-level Whisper model cache — loaded once, reused across renders
_whisper_model_cache: dict[str, Any] = {}


def _get_whisper_model(model_name: str = "base") -> Any:
    """Load Whisper model once and cache it in memory."""
    if model_name not in _whisper_model_cache:
        try:
            import whisper
        except ImportError as exc:
            raise ImportError("Whisper is not installed. Run: pip install openai-whisper") from exc

        device = "cuda" if _cuda_available() else "cpu"
        logger.info("Loading Whisper model '%s' on %s (first time)...", model_name, device)
        try:
            _whisper_model_cache[model_name] = whisper.load_model(model_name, device=device)
            logger.info("Whisper model '%s' loaded and cached.", model_name)
        except Exception as exc:
            logger.error("Failed to load Whisper model '%s': %s", model_name, exc)
            raise RenderingError(f"Failed to load Whisper model: {exc}") from exc
    return _whisper_model_cache[model_name]


def _cuda_available() -> bool:
    try:
        import torch
        return torch.cuda.is_available()
    except ImportError:
        return False


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
    model = _get_whisper_model("base")
    language_code = {"hindi": "hi", "english": "en"}.get(language.lower(), language)

    try:
        result = model.transcribe(audio_path, word_timestamps=True, language=language_code)
    except Exception as exc:
        logger.error("Whisper transcription failed for %s: %s", audio_path, exc)
        raise RenderingError(f"Subtitle generation failed: {exc}") from exc

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
        # Check if loudness is valid
        if loudness <= -70.0:  # Silence or invalid
            logger.warning("Audio has invalid loudness (%f), skipping normalization", loudness)
            return
        normalized = pyln.normalize.loudness(data, loudness, target_lufs)
        sf.write(audio_path, normalized, rate)
    except ImportError:
        logger.warning("pyloudnorm not installed, skipping audio normalization")
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
        VideoFileClip,
        concatenate_videoclips,
    )
    return VideoFileClip, AudioFileClip, CompositeAudioClip, concatenate_videoclips


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
    return concatenate_videoclips([video] * loops, method="chain").subclipped(0, duration)


# ---------------------------------------------------------------------------
# Core rendering logic
# ---------------------------------------------------------------------------

def _burn_subtitles_ffmpeg(
    input_path: Path,
    subtitle_path: Path,
    output_path: Path,
    video_format: str = "long",
) -> None:
    """
    Burn SRT subtitles into video using FFmpeg subtitles filter.
    Far faster than MoviePy TextClip — no per-word Python objects.
    """
    # Validate input file exists
    if not input_path.exists():
        raise RenderingError(f"Input video file not found: {input_path}")
    
    # Validate subtitle file exists
    if not subtitle_path.exists():
        raise RenderingError(f"Subtitle file not found: {subtitle_path}")
    
    font_size = 20 if video_format == "long" else 26
    margin_v = 60 if video_format == "shorts" else 40

    force_style = (
        f"FontName=Arial,FontSize={font_size},Bold=1,"
        f"PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
        f"BorderStyle=1,Outline=2,Shadow=0,"
        f"Alignment=2,MarginV={margin_v}"
    )

    srt_escaped = str(subtitle_path).replace("\\", "/").replace(":", "\\:")

    # Filter chain: scale to even dimensions, then burn subtitles
    # We use trunc(iw/2)*2 to ensure dimensions are even, which libx264 requires.
    vf = (
        f"scale='trunc(iw/2)*2':'trunc(ih/2)*2',"
        f"subtitles='{srt_escaped}':force_style='{force_style}'"
    )
    
    cmd = [
        settings.ffmpeg_binary, "-y",
        "-i", str(input_path),
        "-vf", vf,
        "-c:v", "libx264",
        "-preset", "medium", # Better compression than superfast
        "-crf", "18",
        "-c:a", "copy",
        str(output_path),
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            error_msg = result.stderr[-500:] if result.stderr else "Unknown error"
            logger.error("FFmpeg subtitle burn failed: %s", error_msg)
            raise RenderingError(f"FFmpeg subtitle burn failed: {error_msg}")
    except subprocess.TimeoutExpired:
        logger.error("FFmpeg subtitle burn timed out after 600 seconds")
        raise RenderingError("FFmpeg subtitle burn timed out")
    except FileNotFoundError:
        logger.error("FFmpeg not found at '%s'", settings.ffmpeg_binary)
        raise RenderingError(f"FFmpeg not found at '{settings.ffmpeg_binary}'. Please install FFmpeg.")
    except Exception as exc:
        logger.error("Unexpected error during FFmpeg subtitle burn: %s", exc)
        raise RenderingError(f"FFmpeg subtitle burn error: {exc}") from exc


def _render_with_moviepy(project: Project, render: Render, db: Session) -> None:
    VideoFileClip, AudioFileClip, CompositeAudioClip, concatenate_videoclips = _import_moviepy()

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
    scene_count = len(project.scenes)
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
        target_duration = min(max(scene.duration_seconds, 0.5), video.duration)
        video = video.subclipped(0, target_duration)

        # Scale to fill the target size, then center-crop
        if video.w / video.h < size[0] / size[1]:
            video = video.resized(height=size[1])
        else:
            video = video.resized(width=size[0])
        video = video.cropped(x_center=video.w / 2, y_center=video.h / 2, width=size[0], height=size[1])
        clips.append(video)
        logger.info(
            "Render clip for scene %d: path=%s duration=%.2fs target=%.2fs",
            scene.scene_index,
            selected.local_path,
            video.duration,
            target_duration,
        )

    if not clips:
        raise RenderingError("No video clips to render.")

    if len(clips) != scene_count:
        logger.warning(
            "Project %d has %d scenes but only %d clips were loaded for rendering",
            project.id,
            scene_count,
            len(clips),
        )

    logger.info(
        "Concatenating %d clips for project %d (master voiceover duration: %.2fs)",
        len(clips),
        project.id,
        master_duration,
    )
    final = concatenate_videoclips(clips, method="chain")
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

    # Write raw video WITHOUT subtitles first (much faster — no TextClip objects)
    raw_output = storage.get_render_path().with_stem("raw_render")
    raw_output.parent.mkdir(parents=True, exist_ok=True)

    fps = 30 if project.video_format == "shorts" else 60

    try:
        logger.info("Starting render with GPU acceleration (h264_nvenc)...")
        final.write_videofile(
            str(raw_output),
            fps=fps,
            codec="h264_nvenc",
            audio_codec="aac",
            preset="p4",
            threads=4,
            logger=None,
        )
    except Exception as exc:
        logger.warning("GPU render failed, falling back to CPU (libx264). Error: %s", exc)
        final.write_videofile(
            str(raw_output),
            fps=fps,
            codec="libx264",
            audio_codec="aac",
            preset="superfast",
            threads=4,
            logger=None,
        )

    output = storage.get_render_path()

    # Burn subtitles via FFmpeg (10x faster than TextClip overlays)
    if project.subtitles_enabled and render.subtitle_path and Path(render.subtitle_path).exists():
        try:
            _burn_subtitles_ffmpeg(
                input_path=raw_output,
                subtitle_path=Path(render.subtitle_path),
                output_path=output,
                video_format=project.video_format,
            )
            raw_output.unlink(missing_ok=True)
        except RenderingError as exc:
            logger.error("Subtitle burn failed, using raw video without subtitles: %s", exc)
            raw_output.rename(output)
            render.subtitle_path = None  # Clear subtitle path since burn failed
    else:
        raw_output.rename(output)

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


# ---------------------------------------------------------------------------
# Image story rendering logic
# ---------------------------------------------------------------------------

def _scene_time_boundaries(scenes, voiceover_path: str) -> list[tuple[Any, float, float]]:
    """Compute start/end times for each scene based on voiceover audio duration."""
    import soundfile as sf
    data, sample_rate = sf.read(voiceover_path)
    total_duration = len(data) / sample_rate

    # Estimate each scene's proportion based on voiceover text word count
    word_counts = [len(s.voiceover_text.split()) for s in scenes]
    total_words = max(sum(word_counts), 1)
    proportions = [wc / total_words for wc in word_counts]

    # Allocate total duration minus silence gaps (150ms between scenes)
    gap = 0.150
    available_duration = total_duration - gap * max(len(scenes) - 1, 0)
    if available_duration <= 0:
        available_duration = total_duration

    boundaries = []
    current_time = 0.0
    for i, scene in enumerate(scenes):
        scene_duration = proportions[i] * available_duration
        end_time = current_time + scene_duration
        boundaries.append((scene, current_time, end_time))
        current_time = end_time + gap
    return boundaries


def _build_ken_burns_clip(image_path: str, duration: float, size: tuple[int, int]):
    """Build an ImageClip with gentle Ken Burns zoom + center crop to target size."""
    from moviepy import ImageClip, VideoClip
    import numpy as np

    clip = ImageClip(image_path).with_duration(duration)

    # Initial scale to cover target resolution
    w_orig, h_orig = clip.size
    ratio = max(size[0] / w_orig, size[1] / h_orig)
    clip = clip.resized(ratio)

    def scale(t):
        return 1.0 + 0.10 * (t / max(duration, 0.01))

    # Dynamic zoom (MoviePy 2.x Resize effect supports functions)
    clip = clip.resized(lambda t: scale(t))

    # Dynamic center crop via transform (Crop effect doesn't support functions in v2)
    def crop_frame(get_frame, t):
        frame = get_frame(t)
        h, w = frame.shape[:2]
        x1 = max(0, (w - size[0]) // 2)
        y1 = max(0, (h - size[1]) // 2)
        return frame[y1 : y1 + size[1], x1 : x1 + size[0]]

    clip = clip.transform(crop_frame, keep_duration=True)
    clip.size = size  # Ensure the clip size is explicitly set for composition
    return clip


def render_image_story_video(project_id: int) -> None:
    """Background task for image_story projects."""
    db = SessionLocal()
    try:
        from moviepy import (
            AudioFileClip,
            CompositeAudioClip,
            concatenate_videoclips,
        )

        project = db.get(Project, project_id)
        if not project or not project.render:
            logger.error("render_image_story_video called for missing project/render id=%d", project_id)
            return

        render = project.render
        render.render_status = "rendering"
        render.error_message = None
        project.status = ProjectStatus.rendering.value
        db.commit()

        try:
            if project.video_format != "image_story":
                raise RenderingError("Project is not image_story format")

            scenes = sorted(project.scenes, key=lambda s: s.scene_index)
            missing = []
            for scene in scenes:
                if not scene.uploaded_image_path:
                    missing.append(f"Scene {scene.scene_index} has no uploaded image")
                elif not Path(scene.uploaded_image_path).exists():
                    missing.append(f"Scene {scene.scene_index} image file missing on disk")
            if missing:
                raise RenderingError("; ".join(missing))

            voiceover_path = render.voiceover_path
            if not voiceover_path or not Path(voiceover_path).exists():
                raise RenderingError(f"Voiceover file missing on disk: {voiceover_path}")

            storage = ProjectStorage(project.id)
            subtitle_path = storage.get_subtitle_path()
            _generate_whisper_subtitles(voiceover_path, subtitle_path, language=project.subtitle_language)
            render.subtitle_path = str(subtitle_path)
            logger.info("Whisper subtitles generated: %s", subtitle_path)

            time_boundaries = _scene_time_boundaries(scenes, voiceover_path)

            size = IMAGE_STORY_RESOLUTION
            image_clips = []
            for scene, start, end in time_boundaries:
                duration = end - start
                clip = _build_ken_burns_clip(scene.uploaded_image_path, duration, size)
                image_clips.append(clip)
                logger.info("Built image clip for scene %d: duration=%.2fs", scene.scene_index, duration)

            if not image_clips:
                raise RenderingError("No image clips to render")

            concatenated = concatenate_videoclips(image_clips, method="compose")
            voiceover_audio = AudioFileClip(voiceover_path).subclipped(0, concatenated.duration)

            music_path = render.music_path if render.music_path and Path(render.music_path).exists() else None
            if not music_path:
                music_path = _load_background_music(render.music_name)

            if music_path:
                music = _loop_audio_to_duration(AudioFileClip(music_path), concatenated.duration).with_volume_scaled(0.08)
                final_audio = CompositeAudioClip([voiceover_audio, music])
                final_video = concatenated.with_audio(final_audio)
            else:
                final_video = concatenated.with_audio(voiceover_audio)

            raw_output = storage.get_render_path().with_stem("raw_render")
            raw_output.parent.mkdir(parents=True, exist_ok=True)

            try:
                logger.info("Starting image story render with GPU acceleration (h264_nvenc)...")
                final_video.write_videofile(
                    str(raw_output),
                    fps=30,
                    codec="h264_nvenc",
                    audio_codec="aac",
                    preset="p4",
                    threads=4,
                    logger=None,
                )
            except Exception as exc:
                logger.warning("GPU render failed, falling back to CPU (libx264). Error: %s", exc)
                final_video.write_videofile(
                    str(raw_output),
                    fps=30,
                    codec="libx264",
                    audio_codec="aac",
                    preset="superfast",
                    threads=4,
                    logger=None,
                )

            output = storage.get_render_path()
            if project.subtitles_enabled and render.subtitle_path and Path(render.subtitle_path).exists():
                try:
                    _burn_subtitles_ffmpeg(
                        input_path=raw_output,
                        subtitle_path=Path(render.subtitle_path),
                        output_path=output,
                        video_format="long",
                    )
                    raw_output.unlink(missing_ok=True)
                except RenderingError as exc:
                    logger.error("Subtitle burn failed for image story, using raw video: %s", exc)
                    raw_output.rename(output)
                    render.subtitle_path = None
            else:
                raw_output.rename(output)

            render.render_path = str(output)
            render.render_status = "complete"
            project.status = ProjectStatus.complete.value
            project.current_stage = "render"
            logger.info("Image story project %d rendered successfully", project_id)
        except Exception as exc:
            logger.exception("Image story render failed for project %d", project_id)
            render.render_status = "error"
            render.error_message = str(exc)
            project.status = ProjectStatus.error.value

        db.commit()
    finally:
        db.close()
