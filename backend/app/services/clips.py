"""
Clip service — fetches and downloads stock video clips from Pexels.

Design:
- fetch_clip_options() returns clip metadata for user selection (no download yet).
- download_selected_clip() downloads the chosen clip and validates content-type.
- Both raise ClipServiceError on failure — callers convert to HTTP 502.
"""

import logging
import os
import re
import socket
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import urlparse

import requests

from ..config import settings
from ..models import Clip, Project, Scene
from ..services.ai import score_clips_for_scene
from ..storage import ProjectStorage

logger = logging.getLogger(__name__)


class ClipServiceError(RuntimeError):
    pass


# Private IP ranges to block for SSRF protection
PRIVATE_IP_PATTERNS = [
    r'^127\.',  # Loopback
    r'^10\.',   # Private Class A
    r'^172\.(1[6-9]|2[0-9]|3[0-1])\.',  # Private Class B
    r'^192\.168\.',  # Private Class C
    r'^169\.254\.',  # Link-local
    r'^::1$',  # IPv6 loopback
    r'^fc00:',  # IPv6 private
    r'^fe80:',  # IPv6 link-local
]


def _is_safe_url(url: str) -> bool:
    """
    Validate URL to prevent SSRF attacks.
    Blocks internal/private IPs and ensures proper scheme.
    """
    try:
        parsed = urlparse(url)
        
        # Must be http or https
        if parsed.scheme not in ('http', 'https'):
            return False
        
        # Block if no hostname
        if not parsed.hostname:
            return False
        
        # Block localhost variants
        hostname_lower = parsed.hostname.lower()
        if hostname_lower in ('localhost', 'localhost.localdomain'):
            return False
        
        # Block private IP ranges
        for pattern in PRIVATE_IP_PATTERNS:
            if re.match(pattern, hostname_lower):
                return False
        
        # Block domain that resolves to private IP
        try:
            ip = socket.gethostbyname(parsed.hostname)
            for pattern in PRIVATE_IP_PATTERNS:
                if re.match(pattern, ip):
                    logger.warning("URL hostname resolves to private IP: %s -> %s", parsed.hostname, ip)
                    return False
        except socket.gaierror:
            # DNS resolution failed - allow but will fail later
            pass
        
        return True
    except Exception as exc:
        logger.error("URL validation failed for %s: %s", url, exc)
        return False


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
            headers={"Authorization": settings.pexels_api_key}
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


def _fetch_coverr_clips(keyword: str, project: Project, per_page: int = 6) -> list[dict]:
    """
    Search Coverr.co for CC0 stock clips. No API key required.
    Coverr JSON API: https://coverr.co/api/videos?keywords=<query>&page=1
    """
    orientation_filter = "portrait" if project.video_format == "shorts" else "landscape"
    try:
        response = requests.get(
            "https://coverr.co/api/videos",
            params={
                "keywords": keyword,
                "page": 1,
                "per_page": per_page,
            },
            headers={"User-Agent": "YMaker/1.0"}
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("Coverr connection failed for '%s': %s", keyword, exc)
        return []

    items = []
    for video in response.json().get("hits", []):
        base_filename = video.get("base_filename")
        if not base_filename:
            continue
        mp4_url = f"https://cdn.coverr.co/videos/{base_filename}/1080p.mp4"
        width = video.get("max_width") or video.get("width") or 1920
        height = video.get("max_height") or video.get("height") or 1080
        is_portrait = height > width
        if orientation_filter == "portrait" and not is_portrait:
            continue
        if orientation_filter == "landscape" and is_portrait:
            continue
        duration = video.get("duration")
        try:
            duration = float(duration) if duration is not None else None
        except (ValueError, TypeError):
            duration = None
        items.append({
            "source_id": str(video.get("id", "")),
            "source": "coverr",
            "url": mp4_url,
            "preview_url": video.get("poster") or video.get("thumbnail"),
            "image_url": video.get("poster") or video.get("thumbnail"),
            "width": width,
            "height": height,
            "duration": duration,
            "name": video.get("title") or keyword,
        })
    return items[:per_page]


def _fetch_mixkit_clips(keyword: str, project: Project, per_page: int = 6) -> list[dict]:
    """
    Search Mixkit for free stock clips via HTML scraping.
    Mixkit has no public JSON API — we extract video IDs from embedded CDN URLs.
    """
    import re

    try:
        response = requests.get(
            "https://mixkit.co/free-stock-video/",
            params={"q": keyword},
            headers={"User-Agent": "Mozilla/5.0 (compatible; YMaker/1.0)"}
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("Mixkit connection failed for '%s': %s", keyword, exc)
        return []

    html = response.text

    # Extract video IDs from embedded CDN URLs: assets.mixkit.co/videos/{id}/{id}-360.mp4
    seen_ids: set[str] = set()
    items: list[dict] = []
    for m in re.finditer(
        r"(?:assets\.mixkit\.co|mixkit\.co)/videos/(\d+)/\1-\d+\.mp4", html
    ):
        vid_id = m.group(1)
        if vid_id in seen_ids:
            continue
        seen_ids.add(vid_id)

        # Try to find a title from nearby alt attributes
        context_start = max(0, m.start() - 800)
        context = html[context_start:m.end()]
        alt_match = re.search(r'alt="([^"]{5,80})"', context)
        title = alt_match.group(1) if alt_match else keyword

        # Skip generic / UI alt texts
        if title in ("Mixkit home.", "Envato Elements", "Open menu", "Close menu", "Search"):
            title = keyword

        # Build CDN URLs — 720p is a good balance of quality vs size
        base = f"https://assets.mixkit.co/videos/{vid_id}/{vid_id}"
        items.append({
            "source_id": vid_id,
            "source": "mixkit",
            "url": f"{base}-720.mp4",
            "preview_url": f"{base}-360.mp4",
            "image_url": f"{base}-360.mp4",
            "width": 1280,
            "height": 720,
            "duration": None,
            "name": title,
        })

    return items[:per_page]


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
            }
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
            headers={"Authorization": settings.pexels_api_key}
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
            params={"key": settings.pixabay_api_key, "id": clip.source_id}
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("Unable to refresh Pixabay clip %s: %s", clip.source_id, exc)
        return None
    hits = response.json().get("hits", [])
    return _pixabay_item(hits[0]) if hits else None


def _refresh_clip_url(clip: Clip) -> None:
    """Refresh provider download URLs. Coverr/Mixkit are static CDN — no refresh needed."""
    if clip.source in ("coverr", "mixkit"):
        return
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


def _generate_keyword_variants(description: str, original_keyword: str) -> list[str]:
    """
    Generate 3 progressively simpler keyword variants to use as fallbacks.
    Does NOT call AI — uses simple heuristics to avoid extra latency.
    """
    words = original_keyword.lower().split()
    variants = []
    if len(words) > 2:
        variants.append(" ".join(words[:-1]))
    if len(words) > 1:
        variants.append(" ".join(words[:2]))
    variants.append(words[0])
    seen = {original_keyword.lower()}
    return [v for v in variants if v not in seen]


def fetch_clip_options(scene: Scene, project: Project, per_page: int = 6) -> list[dict]:
    """Search stock providers for clips matching the scene keyword, then AI-rank them."""
    provider = project.clip_provider or settings.clip_provider

    # Validate visual_keyword to prevent injection
    if not scene.visual_keyword or len(scene.visual_keyword.strip()) < 2:
        logger.warning("Scene %d has invalid visual_keyword, skipping clip fetch", scene.scene_index)
        return []

    # Sanitize keyword to prevent potential issues
    keyword = scene.visual_keyword.strip()[:200]  # Limit length

    pexels_items: list[dict] = []
    pixabay_items: list[dict] = []
    coverr_items: list[dict] = []
    mixkit_items: list[dict] = []

    if provider in ("pexels", "hybrid"):
        pexels_items = _fetch_pexels_clips(keyword, project, min(per_page, 6))

    if provider in ("pixabay", "hybrid"):
        pixabay_items = _fetch_pixabay_clips(keyword, project, 6)

    if provider in ("coverr", "hybrid", "free"):
        coverr_items = _fetch_coverr_clips(keyword, project, 6)

    if provider in ("mixkit", "hybrid", "free"):
        mixkit_items = _fetch_mixkit_clips(keyword, project, 6)

    # Merge: interleave sources for diversity, deduplicate by url
    seen_urls: set[str] = set()
    items: list[dict] = []
    for group in [pexels_items, coverr_items, pixabay_items, mixkit_items]:
        for item in group:
            url = item.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                items.append(item)

    # Fallback with keyword variants if nothing found
    if not items:
        logger.warning("No clips found for keyword '%s' (scene %d)", keyword, scene.scene_index)
        keyword_variants = _generate_keyword_variants(scene.description, keyword)
        for fallback_keyword in keyword_variants:
            # Sanitize fallback keyword as well
            fallback_keyword = fallback_keyword.strip()[:200]
            logger.info("Retrying with fallback keyword '%s' for scene %d", fallback_keyword, scene.scene_index)
            if provider in ("pexels", "hybrid"):
                items += _fetch_pexels_clips(fallback_keyword, project, 4)
            if provider in ("coverr", "hybrid", "free"):
                items += _fetch_coverr_clips(fallback_keyword, project, 4)
            if provider in ("pixabay", "hybrid"):
                items += _fetch_pixabay_clips(fallback_keyword, project, 4)
            if items:
                break

    if not items:
        return []

    # AI scoring using thumbnail URLs (multimodal-aware scoring)
    try:
        scoring_input = [
            {
                "clip_id": str(index),
                "name": clip.get("name") or "",
                "source": clip.get("source", "unknown"),
                "duration": clip.get("duration"),
                "thumbnail": clip.get("image_url") or clip.get("preview_url") or "",
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

    return items[:10]


def download_selected_clip(project_id: int, clip: Clip) -> str:
    """
    Download the selected clip from provider to local project storage.

    Validates that the response is actually a video file before writing,
    preventing silent corruption where an HTML error page gets saved as .mp4.
    """
    # Validate URL to prevent SSRF attacks
    if not clip.url or not _is_safe_url(clip.url):
        raise ClipServiceError(f"Invalid or unsafe clip URL: {clip.url}")

    storage = ProjectStorage(project_id)
    target = storage.get_clip_path(clip.id)

    last_error: Exception | None = None
    for attempt in range(2):
        tmp_path: Path | None = None
        if attempt:
            _refresh_clip_url(clip)
        try:
            response = requests.get(clip.url, stream=True)
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
