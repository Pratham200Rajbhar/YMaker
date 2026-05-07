"""
Clip service — fetches and downloads stock video clips from Pexels.

Design:
- fetch_clip_options() returns clip metadata for user selection (no download yet).
- download_selected_clip() downloads the chosen clip and validates content-type.
- Both raise ClipServiceError on failure — callers convert to HTTP 502.
"""

import logging
from pathlib import Path

import requests

from ..config import settings
from ..models import Clip, Project, Scene
from ..storage import ProjectStorage

logger = logging.getLogger(__name__)


class ClipServiceError(RuntimeError):
    pass


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


def fetch_clip_options(scene: Scene, project: Project, per_page: int = 4) -> list[dict]:
    """Search Pexels for stock clips matching the scene keyword."""
    if not settings.pexels_api_key:
        raise ClipServiceError("PEXELS_API_KEY is not configured.")

    orientation = "portrait" if project.video_format == "shorts" else "landscape"
    try:
        response = requests.get(
            "https://api.pexels.com/videos/search",
            params={
                "query": scene.visual_keyword,
                "orientation": orientation,
                "per_page": per_page,
            },
            headers={"Authorization": settings.pexels_api_key},
            timeout=20,
        )
        response.raise_for_status()
    except requests.HTTPError as exc:
        raise ClipServiceError(f"Pexels API error ({exc.response.status_code}) for '{scene.visual_keyword}'") from exc
    except requests.RequestException as exc:
        raise ClipServiceError(f"Pexels connection failed: {exc}") from exc

    items = []
    for video in response.json().get("videos", []):
        best = _best_file(video)
        if not best.get("link"):
            continue
        items.append(
            {
                "pexels_id": str(video["id"]),
                "url": best["link"],
                "preview_url": video.get("video_pictures", [{}])[0].get("picture"),
                "image_url": video.get("image"),
                "width": best.get("width"),
                "height": best.get("height"),
                "duration": video.get("duration"),
                "name": video.get("url", "").split("/video/")[1].split("/")[0].replace("-", " ") if "/video/" in video.get("url", "") else "Stock Video",
            }
        )

    if not items:
        logger.warning("No clips found for keyword '%s' (scene %d)", scene.visual_keyword, scene.scene_index)

    return items


def download_selected_clip(project_id: int, clip: Clip) -> str:
    """
    Download the selected clip from Pexels to local project storage.

    Validates that the response is actually a video file before writing,
    preventing silent corruption where an HTML error page gets saved as .mp4.
    """
    storage = ProjectStorage(project_id)
    target = storage.get_clip_path(clip.id)

    try:
        response = requests.get(clip.url, timeout=90, stream=True)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise ClipServiceError(f"Failed to download clip {clip.id}: {exc}") from exc

    content_type = response.headers.get("Content-Type", "")
    if not content_type.startswith("video/"):
        raise ClipServiceError(
            f"Clip {clip.id} returned unexpected content type '{content_type}' — "
            "the Pexels URL may have expired. Re-fetch clips and try again."
        )

    with target.open("wb") as fh:
        for chunk in response.iter_content(chunk_size=1024 * 256):
            fh.write(chunk)

    logger.info("Downloaded clip %d → %s", clip.id, target)
    return str(target)
