"""
Clip service — fetches and downloads stock video clips from Pexels.

Design:
- fetch_clip_options() returns clip metadata for user selection (no download yet).
- download_selected_clip() downloads the chosen clip and validates content-type.
- Both raise ClipServiceError on failure — callers convert to HTTP 502.
"""

import logging
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

import requests

from ..config import settings
from ..models import Clip, Project, Scene
from ..services.ai import optimize_visual_keyword, score_clips_for_scene
from ..storage import ProjectStorage

logger = logging.getLogger(__name__)


class ClipServiceError(RuntimeError):
    pass


VIDEO_CONTENT_TYPES = {
    "application/octet-stream",
    "binary/octet-stream",
    "video/mp4",
    "video/quicktime",
    "video/x-m4v",
}


def _best_file(video: dict) -> dict:
    """
    Pick the highest-resolution MP4 from a Pexels video's file list.
    Falls back to the first available file if no MP4 found.
    """
    files = sorted(
        video.get("video_files", []),
        key=lambda item: (item.get("width") or 0) * (item.get("height") or 0),
        reverse=True,
    )
    mp4s = [f for f in files if f.get("file_type") == "video/mp4" and f.get("link")]
    return mp4s[0] if mp4s else (files[0] if files else {})


def _clip_name_from_pexels(video: dict) -> str:
    url = video.get("url", "")
    if "/video/" in url:
        return url.split("/video/")[1].split("/")[0].replace("-", " ")
    return video.get("user", {}).get("name") or "Pexels Video"


def _pexels_item(video: dict) -> dict | None:
    best = _best_file(video)
    if not best.get("link"):
        return None
    return {
        "source_id": str(video["id"]),
        "source": "pexels",
        "url": best["link"],
        "preview_url": video.get("video_pictures", [{}])[0].get("picture"),
        "image_url": video.get("image"),
        "width": best.get("width"),
        "height": best.get("height"),
        "duration": video.get("duration"),
        "name": _clip_name_from_pexels(video),
    }


def _fetch_pexels_clips(keyword: str, project: Project, per_page: int = 6) -> list[dict]:
    """Search Pexels for stock clips matching a keyword."""
    if not settings.pexels_api_key:
        logger.warning("PEXELS_API_KEY is not configured; skipping Pexels clip search.")
        return []

    orientation = "portrait" if project.video_format == "shorts" else "landscape"
    try:
        response = requests.get(
            "https://api.pexels.com/videos/search",
            params={
                "query": keyword,
                "orientation": orientation,
                "per_page": per_page,
            },
            headers={"Authorization": settings.pexels_api_key},
            timeout=20,
        )
        response.raise_for_status()
    except requests.HTTPError as exc:
        logger.warning("Pexels API error (%s) for '%s'", exc.response.status_code, keyword)
        return []
    except requests.RequestException as exc:
        logger.warning("Pexels connection failed for '%s': %s", keyword, exc)
        return []

    items = []
    for video in response.json().get("videos", []):
        item = _pexels_item(video)
        if item:
            items.append(item)
    return items


def _best_pixabay_video(video: dict) -> dict:
    videos = video.get("videos", {})
    for quality in ("large", "medium", "small", "tiny"):
        candidate = videos.get(quality) or {}
        if candidate.get("url"):
            return candidate
    return {}


def _pixabay_item(video: dict) -> dict | None:
    best = _best_pixabay_video(video)
    if not best.get("url"):
        return None
    tags = video.get("tags") or "Pixabay Video"
    image_url = f"https://i.vimeocdn.com/video/{video.get('picture_id')}_640x360.jpg" if video.get("picture_id") else None
    return {
        "source_id": str(video["id"]),
        "source": "pixabay",
        "url": best["url"],
        "preview_url": image_url,
        "image_url": image_url,
        "width": best.get("width"),
        "height": best.get("height"),
        "duration": video.get("duration"),
        "name": tags,
    }


def _fetch_pixabay_clips(keyword: str, project: Project, per_page: int = 6) -> list[dict]:
    """Search Pixabay Videos for stock clips matching the keyword."""
    if not settings.pixabay_api_key:
        logger.warning("PIXABAY_API_KEY is not configured; skipping Pixabay clip search.")
        return []

    orientation = "vertical" if project.video_format == "shorts" else "horizontal"
    try:
        response = requests.get(
            "https://pixabay.com/api/videos/",
            params={
                "key": settings.pixabay_api_key,
                "q": keyword,
                "orientation": orientation,
                "per_page": per_page,
            },
            timeout=20,
        )
        response.raise_for_status()
    except requests.HTTPError as exc:
        logger.warning("Pixabay API error (%s) for '%s'", exc.response.status_code, keyword)
        return []
    except requests.RequestException as exc:
        logger.warning("Pixabay connection failed for '%s': %s", keyword, exc)
        return []

    items = []
    for video in response.json().get("hits", []):
        item = _pixabay_item(video)
        if item:
            items.append(item)
    return items


def _refresh_pexels_clip(clip: Clip) -> dict | None:
    if not settings.pexels_api_key:
        return None
    try:
        response = requests.get(
            f"https://api.pexels.com/videos/videos/{clip.source_id}",
            headers={"Authorization": settings.pexels_api_key},
            timeout=20,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("Unable to refresh Pexels clip %s: %s", clip.source_id, exc)
        return None
    return _pexels_item(response.json())


def _refresh_pixabay_clip(clip: Clip) -> dict | None:
    if not settings.pixabay_api_key:
        return None
    try:
        response = requests.get(
            "https://pixabay.com/api/videos/",
            params={"key": settings.pixabay_api_key, "id": clip.source_id},
            timeout=20,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("Unable to refresh Pixabay clip %s: %s", clip.source_id, exc)
        return None
    hits = response.json().get("hits", [])
    return _pixabay_item(hits[0]) if hits else None


def _refresh_clip_url(clip: Clip) -> None:
    """Refresh provider download URLs because stock CDN links can expire."""
    refreshed = _refresh_pixabay_clip(clip) if clip.source == "pixabay" else _refresh_pexels_clip(clip)
    if not refreshed:
        return
    clip.url = refreshed["url"]
    clip.preview_url = refreshed.get("preview_url")
    clip.image_url = refreshed.get("image_url")
    clip.width = refreshed.get("width")
    clip.height = refreshed.get("height")
    clip.duration = refreshed.get("duration")
    clip.name = refreshed.get("name")


def _validate_video_file(path: Path) -> None:
    try:
        from moviepy import VideoFileClip

        with VideoFileClip(str(path)) as video:
            if not video.duration or video.duration <= 0 or not video.w or not video.h:
                raise ClipServiceError(f"Downloaded clip is not a valid video: {path.name}")
    except ClipServiceError:
        raise
    except Exception as exc:
        raise ClipServiceError(f"Downloaded clip failed video validation: {exc}") from exc


def fetch_clip_options(scene: Scene, project: Project, per_page: int = 6) -> list[dict]:
    """Search stock providers for clips matching the scene keyword, then AI-rank them."""
    provider = project.clip_provider or settings.clip_provider
    
    pexels_items = []
    pixabay_items = []
    
    if provider in ("pexels", "hybrid"):
        pexels_items = _fetch_pexels_clips(scene.visual_keyword, project, min(per_page, 6))
    
    if provider in ("pixabay", "hybrid"):
        pixabay_items = _fetch_pixabay_clips(scene.visual_keyword, project, 6)
        
    items = pexels_items + pixabay_items

    if not items:
        logger.warning("No clips found for keyword '%s' (scene %d)", scene.visual_keyword, scene.scene_index)
        try:
            fallback_keyword = optimize_visual_keyword(scene.description, scene.visual_keyword)
            logger.info("Retrying fetch with fallback keyword '%s' for scene %d", fallback_keyword, scene.scene_index)
            
            if provider in ("pexels", "hybrid"):
                items += _fetch_pexels_clips(fallback_keyword, project, 6)
            if provider in ("pixabay", "hybrid") and not items:
                 items += _fetch_pixabay_clips(fallback_keyword, project, 6)
        except Exception as exc:
            logger.warning("Fallback keyword clip search failed for scene %d: %s", scene.scene_index, exc)

    if not items:
        return []

    try:
        scoring_input = [
            {
                "clip_id": str(index),
                "name": clip.get("name") or "",
                "source": clip.get("source", "pexels"),
                "duration": clip.get("duration"),
            }
            for index, clip in enumerate(items)
        ]
        scored = score_clips_for_scene(scene.description, scene.visual_keyword, scoring_input)
        score_by_id = {item["clip_id"]: float(item.get("score", 0.0)) for item in scored}
        for index, clip in enumerate(items):
            clip["ai_score"] = score_by_id.get(str(index))
        items.sort(key=lambda clip: clip.get("ai_score") or 0.0, reverse=True)
    except Exception as exc:
        logger.warning("AI clip scoring failed for scene %d: %s", scene.scene_index, exc)

    return items[:8]


def download_selected_clip(project_id: int, clip: Clip) -> str:
    """
    Download the selected clip from Pexels to local project storage.

    Validates that the response is actually a video file before writing,
    preventing silent corruption where an HTML error page gets saved as .mp4.
    """
    storage = ProjectStorage(project_id)
    target = storage.get_clip_path(clip.id)

    last_error: Exception | None = None
    for attempt in range(2):
        tmp_path: Path | None = None
        if attempt:
            _refresh_clip_url(clip)
        try:
            response = requests.get(clip.url, timeout=90, stream=True)
            response.raise_for_status()
            content_type = response.headers.get("Content-Type", "").split(";")[0].lower()
            if content_type and content_type not in VIDEO_CONTENT_TYPES and not content_type.startswith("video/"):
                raise ClipServiceError(f"Clip {clip.id} returned unexpected content type '{content_type}'.")

            target.parent.mkdir(parents=True, exist_ok=True)
            with NamedTemporaryFile("wb", delete=False, dir=target.parent, suffix=".mp4") as tmp:
                tmp_path = Path(tmp.name)
                for chunk in response.iter_content(chunk_size=1024 * 256):
                    if chunk:
                        tmp.write(chunk)

            if tmp_path.stat().st_size < 1024 * 128:
                raise ClipServiceError(f"Downloaded clip {clip.id} is too small to be valid.")
            _validate_video_file(tmp_path)
            os.replace(tmp_path, target)
            logger.info("Downloaded clip %d (%s:%s) -> %s", clip.id, clip.source, clip.source_id, target)
            return str(target)
        except (requests.RequestException, ClipServiceError) as exc:
            last_error = exc
            if tmp_path and tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
            logger.warning("Clip %d download attempt %d failed: %s", clip.id, attempt + 1, exc)

    raise ClipServiceError(f"Failed to download clip {clip.id}: {last_error}")
