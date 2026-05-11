# YMaker — Master Improvement Prompt

Copy this entire prompt into your AI coding agent (Cursor, Claude Code, Copilot Workspace, etc.).
It covers every problem found in the codebase audit and gives exact instructions for each fix.

---

## CONTEXT

You are working on **YMaker** (also called ScriptForge) — a FastAPI + Next.js AI video generation pipeline.
Repo structure: `backend/app/` contains `services/clips.py`, `services/rendering.py`, `services/ai.py`, `services/voice.py`, `config.py`, `models.py`, `schemas.py`, `routers/clips.py`.

Do NOT change `services/voice.py` or any NVIDIA Riva TTS logic. That stays as-is.

Apply ALL changes below. Do not skip any section.

---

## CHANGE 1 — Add Coverr.co and Mixkit as free clip sources (no API key required)

### 1A — `backend/app/services/clips.py`

Add two new fetcher functions AFTER the existing `_fetch_pixabay_clips` function:

```python
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
            headers={"User-Agent": "YMaker/1.0"},
            timeout=20,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("Coverr connection failed for '%s': %s", keyword, exc)
        return []

    items = []
    for video in response.json().get("hits", []):
        # Coverr returns encoded_url (mp4) and cover_url (thumbnail)
        mp4_url = video.get("encoded_url") or video.get("url")
        if not mp4_url:
            continue
        width = video.get("width", 1920)
        height = video.get("height", 1080)
        # Filter by orientation loosely
        is_portrait = height > width
        if orientation_filter == "portrait" and not is_portrait:
            continue
        if orientation_filter == "landscape" and is_portrait:
            continue
        items.append({
            "source_id": str(video.get("id", "")),
            "source": "coverr",
            "url": mp4_url,
            "preview_url": video.get("cover_url"),
            "image_url": video.get("cover_url"),
            "width": width,
            "height": height,
            "duration": video.get("duration"),
            "name": video.get("title") or keyword,
        })
    return items[:per_page]


def _fetch_mixkit_clips(keyword: str, project: Project, per_page: int = 6) -> list[dict]:
    """
    Search Mixkit for free stock clips via their search endpoint.
    Mixkit is free with no API key — uses scrape-friendly JSON search.
    """
    try:
        response = requests.get(
            "https://mixkit.co/free-stock-video/",
            params={"q": keyword},
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; YMaker/1.0)",
                "Accept": "application/json, text/html",
            },
            timeout=20,
        )
        # Mixkit returns HTML; extract JSON-LD or embedded JSON data
        # Try JSON endpoint first
        json_response = requests.get(
            f"https://mixkit.co/api/search/videos?query={requests.utils.quote(keyword)}&per_page={per_page}",
            headers={"User-Agent": "Mozilla/5.0 (compatible; YMaker/1.0)"},
            timeout=20,
        )
        if json_response.status_code == 200:
            data = json_response.json()
            items = []
            for video in data.get("videos", data.get("results", [])):
                mp4_url = (
                    video.get("download_url")
                    or video.get("video_url")
                    or video.get("source", {}).get("url")
                )
                if not mp4_url:
                    continue
                items.append({
                    "source_id": str(video.get("id", "")),
                    "source": "mixkit",
                    "url": mp4_url,
                    "preview_url": video.get("image") or video.get("thumbnail"),
                    "image_url": video.get("image") or video.get("thumbnail"),
                    "width": video.get("width", 1920),
                    "height": video.get("height", 1080),
                    "duration": video.get("duration"),
                    "name": video.get("title") or keyword,
                })
            return items[:per_page]
    except requests.RequestException as exc:
        logger.warning("Mixkit connection failed for '%s': %s", keyword, exc)
    return []
```

### 1B — Update `fetch_clip_options()` in `clips.py`

Replace the provider dispatch block inside `fetch_clip_options`:

```python
def fetch_clip_options(scene: Scene, project: Project, per_page: int = 6) -> list[dict]:
    """Search stock providers for clips matching the scene keyword, then AI-rank them."""
    provider = project.clip_provider or settings.clip_provider

    pexels_items: list[dict] = []
    pixabay_items: list[dict] = []
    coverr_items: list[dict] = []
    mixkit_items: list[dict] = []

    if provider in ("pexels", "hybrid"):
        pexels_items = _fetch_pexels_clips(scene.visual_keyword, project, min(per_page, 6))

    if provider in ("pixabay", "hybrid"):
        pixabay_items = _fetch_pixabay_clips(scene.visual_keyword, project, 6)

    if provider in ("coverr", "hybrid", "free"):
        coverr_items = _fetch_coverr_clips(scene.visual_keyword, project, 6)

    if provider in ("mixkit", "hybrid", "free"):
        mixkit_items = _fetch_mixkit_clips(scene.visual_keyword, project, 6)

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
        logger.warning("No clips found for keyword '%s' (scene %d)", scene.visual_keyword, scene.scene_index)
        keyword_variants = _generate_keyword_variants(scene.description, scene.visual_keyword)
        for fallback_keyword in keyword_variants:
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
```

### 1C — Add `_generate_keyword_variants()` helper in `clips.py`

Add this function before `fetch_clip_options`:

```python
def _generate_keyword_variants(description: str, original_keyword: str) -> list[str]:
    """
    Generate 3 progressively simpler keyword variants to use as fallbacks.
    Does NOT call AI — uses simple heuristics to avoid extra latency.
    """
    words = original_keyword.lower().split()
    variants = []
    # Variant 1: drop last word (broaden)
    if len(words) > 2:
        variants.append(" ".join(words[:-1]))
    # Variant 2: first two words only
    if len(words) > 1:
        variants.append(" ".join(words[:2]))
    # Variant 3: first noun only (first word)
    variants.append(words[0])
    # Deduplicate and exclude original
    seen = {original_keyword.lower()}
    return [v for v in variants if v not in seen]
```

### 1D — Update `download_selected_clip()` to handle Coverr and Mixkit

Add `"coverr"` and `"mixkit"` to the refresh routing in `_refresh_clip_url`:

```python
def _refresh_clip_url(clip: Clip) -> None:
    """Refresh provider download URLs. Coverr/Mixkit are static CDN — no refresh needed."""
    if clip.source in ("coverr", "mixkit"):
        # These are direct CDN links, no refresh needed
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
```

### 1E — Add `"coverr"` and `"mixkit"` and `"free"` to `config.py`

In `Settings` class, update the default for `clip_provider`:

```python
# Clip Provider: "pexels", "pixabay", "coverr", "mixkit", "hybrid" (all), "free" (coverr+mixkit only)
clip_provider: str = "hybrid"
```

---

## CHANGE 2 — Fix rendering performance (replace TextClip subtitles with FFmpeg)

### 2A — `backend/app/services/rendering.py`

Replace the entire karaoke caption overlay block and the `write_videofile` calls at the end of `_render_with_moviepy` with this:

```python
    # Write raw video WITHOUT subtitles first (much faster — no TextClip objects)
    raw_output = storage.get_render_path().with_stem("raw_render")
    raw_output.parent.mkdir(parents=True, exist_ok=True)

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
        _burn_subtitles_ffmpeg(
            input_path=raw_output,
            subtitle_path=Path(render.subtitle_path),
            output_path=output,
            video_format=project.video_format,
        )
        raw_output.unlink(missing_ok=True)
    else:
        raw_output.rename(output)

    render.render_path = str(output)
    db.flush()
    logger.info("Render complete: %s", output)
```

Remove the old `# Karaoke caption overlays` block (the loop building `overlays` list with TextClip) and the `final = CompositeVideoClip(overlays)` line entirely. Keep `final` as the audio-composited clip.

### 2B — Add `_burn_subtitles_ffmpeg()` function in `rendering.py`

Add this function before `_render_with_moviepy`:

```python
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
    import subprocess

    font_size = 20 if video_format == "long" else 26
    margin_v = 60 if video_format == "shorts" else 40

    # ASS override style for clean bold white subtitles with black outline
    force_style = (
        f"FontName=Arial,FontSize={font_size},Bold=1,"
        f"PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
        f"BorderStyle=1,Outline=2,Shadow=0,"
        f"Alignment=2,MarginV={margin_v}"
    )

    # Escape path for FFmpeg filter (Windows backslash + colon issues)
    srt_escaped = str(subtitle_path).replace("\\", "/").replace(":", "\\:")

    cmd = [
        settings.ffmpeg_binary, "-y",
        "-i", str(input_path),
        "-vf", f"subtitles='{srt_escaped}':force_style='{force_style}'",
        "-c:v", "libx264",
        "-preset", "superfast",
        "-crf", "18",
        "-c:a", "copy",
        str(output_path),
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if result.returncode != 0:
            logger.error("FFmpeg subtitle burn failed: %s", result.stderr[-500:])
            # Fallback: just copy without subtitles
            import shutil
            shutil.copy2(input_path, output_path)
    except subprocess.TimeoutExpired:
        logger.error("FFmpeg subtitle burn timed out")
        import shutil
        shutil.copy2(input_path, output_path)
    except FileNotFoundError:
        logger.error("FFmpeg not found at '%s'", settings.ffmpeg_binary)
        import shutil
        shutil.copy2(input_path, output_path)
```

---

## CHANGE 3 — Cache Whisper model (stop cold-loading every render)

### 3A — `backend/app/services/rendering.py`

Add this at module level (after imports, before any functions):

```python
# Module-level Whisper model cache — loaded once, reused across renders
_whisper_model_cache: dict[str, Any] = {}


def _get_whisper_model(model_name: str = "base") -> Any:
    """Load Whisper model once and cache it in memory."""
    if model_name not in _whisper_model_cache:
        import whisper
        device = "cuda" if _cuda_available() else "cpu"
        logger.info("Loading Whisper model '%s' on %s (first time)...", model_name, device)
        _whisper_model_cache[model_name] = whisper.load_model(model_name, device=device)
        logger.info("Whisper model '%s' loaded and cached.", model_name)
    return _whisper_model_cache[model_name]


def _cuda_available() -> bool:
    try:
        import torch
        return torch.cuda.is_available()
    except ImportError:
        return False
```

Add `from typing import Any` to imports if not already present.

### 3B — Update `_generate_whisper_subtitles()` in `rendering.py`

Replace the `model = whisper.load_model(...)` line:

```python
# OLD (remove this):
model = whisper.load_model("base", device="cuda")

# NEW (replace with):
model = _get_whisper_model("base")
```

---

## CHANGE 4 — Fix auto-select to use thumbnail URLs for better AI scoring

### 4A — `backend/app/routers/clips.py`

Update the `auto_select_clips` endpoint's `scenes_data` builder to include thumbnail:

```python
    scenes_data = []
    for scene in project.scenes:
        if not scene.clips:
            continue
        candidates = [
            {
                "clip_id": c.id,
                "name": c.name or "",
                "source": c.source,
                "duration": c.duration,
                "thumbnail": c.image_url or c.preview_url or "",
            }
            for c in scene.clips
        ]
        scenes_data.append({
            "scene_id": scene.id,
            "description": scene.description,
            "visual_keyword": scene.visual_keyword,
            "candidates": candidates,
        })
```

### 4B — Update `select_best_clips()` in `backend/app/services/ai.py`

Replace the system prompt in `select_best_clips`:

```python
def select_best_clips(scenes_data: list[dict]) -> list[dict]:
    """
    Pick the best clip for each scene from candidates.
    Input: list of {scene_id, description, visual_keyword, candidates: [{clip_id, name, source, duration, thumbnail}]}
    Output: list of {scene_id, selected_clip_id}
    """
    system_prompt = (
        "You are an expert video editor choosing B-roll footage. "
        "For each scene, choose the ONE clip that best matches the scene description and visual keyword. "
        "Use the clip name, source tags, and duration to judge relevance. "
        "Prefer clips whose name/tags semantically match the scene action and setting. "
        "Prefer clips with duration >= scene implied duration when available. "
        "Avoid generic clips (sky, abstract, bokeh) when a specific match exists. "
        "Return ONLY a JSON object with a 'selections' array."
    )
    user_prompt = f"Scenes and their clip candidates:\n{json.dumps(scenes_data, indent=2)}"
    result = _generate_json(system_prompt, user_prompt, CLIP_SELECTOR_SCHEMA)
    return result.get("selections", [])
```

Also update `score_clips_for_scene()` system prompt:

```python
def score_clips_for_scene(scene_description: str, scene_keyword: str, clips: list[dict]) -> list[dict]:
    """
    Score candidate clips for a single scene by visual relevance.
    Input clips contain {clip_id, name, source, duration, thumbnail}.
    """
    system_prompt = (
        "You are an expert video editor scoring B-roll stock footage for visual relevance. "
        "Score each clip 0.0–1.0 based on how well its name, tags, and source metadata match the scene. "
        "Score criteria: "
        "1.0 = exact subject+action+setting match. "
        "0.7 = correct subject, similar action. "
        "0.4 = related domain but vague. "
        "0.1 = generic/unrelated. "
        "Penalize clips with generic names like 'untitled', 'video', single words. "
        "Boost clips whose name contains words from the visual keyword. "
        "Return ONLY a JSON object with a scored_clips array."
    )
    user_prompt = (
        f"Scene description:\n{scene_description}\n\n"
        f"Visual keyword:\n{scene_keyword}\n\n"
        f"Clip candidates:\n{json.dumps(clips, indent=2)}"
    )
    result = _generate_json(system_prompt, user_prompt, CLIP_SCORER_SCHEMA)
    scored = result.get("scored_clips", [])
    return sorted(scored, key=lambda item: float(item.get("score", 0.0)), reverse=True)
```

---

## CHANGE 5 — Fix clip download: make it non-blocking (background task)

### 5A — `backend/app/routers/clips.py`

Update the `approve_clips` endpoint to use FastAPI `BackgroundTasks`:

```python
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import JSONResponse

@router.post("/approve", response_model=ProjectOut)
def approve_clips(
    project_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> ProjectOut:
    project = _project(db, project_id)
    if not project.scenes:
        raise HTTPException(status_code=400, detail="No scenes available")

    for scene in project.scenes:
        selected = next((clip for clip in scene.clips if clip.selected), None)
        if not selected:
            raise HTTPException(
                status_code=409,
                detail=f"Scene {scene.scene_index} needs one selected clip",
            )

    # Mark project as downloading so frontend can show progress
    from ..models import ProjectStatus
    project.status = "downloading_clips"
    db.commit()

    # Kick off downloads in background
    background_tasks.add_task(_download_all_clips_bg, project_id)

    db.refresh(project)
    return project_out(project)


def _download_all_clips_bg(project_id: int) -> None:
    """Background task: download all selected clips, then advance stage."""
    from ..database import SessionLocal
    from ..models import Project, ProjectStatus, WorkflowStage

    db = SessionLocal()
    try:
        project = db.get(Project, project_id)
        if not project:
            return

        errors = []
        for scene in project.scenes:
            selected = next((c for c in scene.clips if c.selected), None)
            if not selected or selected.local_path:
                continue
            try:
                selected.local_path = download_selected_clip(project.id, selected)
                db.flush()
            except ClipServiceError as exc:
                errors.append(f"Scene {scene.scene_index}: {exc}")

        if errors:
            project.status = ProjectStatus.error.value
            project.error_message = "; ".join(errors)
        else:
            from ..models import WorkflowStage
            project.current_stage = WorkflowStage.voiceover.value
            project.status = ProjectStatus.approved.value
            project.error_message = None

        db.commit()
    except Exception as exc:
        logger.exception("Background clip download failed for project %d: %s", project_id, exc)
    finally:
        db.close()
```

---

## CHANGE 6 — Add retry with multi-keyword fallback for clip search

### 6A — Already covered in Change 1C (`_generate_keyword_variants`).

Additionally, update `_fetch_pexels_clips` and `_fetch_coverr_clips` to accept a `timeout` parameter and increase it to 25s for reliability:

```python
# In all _fetch_*_clips functions, change timeout=20 to timeout=25
```

---

## CHANGE 7 — Update `config.py` with new provider options

### 7A — `backend/app/config.py`

Add documentation comments and the new providers:

```python
    # Clip Provider options:
    # "pexels"   — Pexels only (requires PEXELS_API_KEY)
    # "pixabay"  — Pixabay only (requires PIXABAY_API_KEY)
    # "coverr"   — Coverr.co only (FREE, no key)
    # "mixkit"   — Mixkit only (FREE, no key)
    # "free"     — Coverr + Mixkit only (fully free, no keys needed)
    # "hybrid"   — All sources combined (best results, keys optional)
    clip_provider: str = "hybrid"
```

---

## CHANGE 8 — Update `ProjectCreate` schema to accept new providers

### 8A — `backend/app/schemas.py`

```python
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
```

---

## CHANGE 9 — Update frontend ClipsStage to show source badges

### 9A — `frontend/components/stages/ClipsStage.tsx`

In the clip card rendering, add a source badge showing the clip origin:

```tsx
// Add a source badge to each clip card showing where it came from
const SOURCE_COLORS: Record<string, string> = {
  pexels: "bg-green-600",
  pixabay: "bg-yellow-600",
  coverr: "bg-blue-600",
  mixkit: "bg-purple-600",
};

// In the clip card JSX, add:
<span className={`text-xs px-2 py-0.5 rounded-full text-white font-medium ${SOURCE_COLORS[clip.source] ?? "bg-gray-600"}`}>
  {clip.source}
</span>
```

---

## CHANGE 10 — Add `"free"` and `"coverr"` and `"mixkit"` provider options to Settings UI

### 10A — `frontend/app/settings/page.tsx`

Add the new options to the clip provider selector (wherever Pexels/Pixabay/hybrid are listed):

```tsx
const CLIP_PROVIDERS = [
  { value: "hybrid", label: "Hybrid (All Sources)" },
  { value: "free", label: "Free Only (Coverr + Mixkit)" },
  { value: "coverr", label: "Coverr.co (Free, CC0)" },
  { value: "mixkit", label: "Mixkit (Free)" },
  { value: "pexels", label: "Pexels (API key required)" },
  { value: "pixabay", label: "Pixabay (API key required)" },
];
```

---

## SUMMARY OF ALL CHANGES

| # | File | What Changed |
|---|------|-------------|
| 1 | `services/clips.py` | Add `_fetch_coverr_clips()`, `_fetch_mixkit_clips()`, `_generate_keyword_variants()` |
| 2 | `services/clips.py` | Update `fetch_clip_options()` to use all 4 sources, interleave results, better fallback |
| 3 | `services/clips.py` | Update `_refresh_clip_url()` to skip refresh for Coverr/Mixkit (static CDN) |
| 4 | `services/rendering.py` | Replace TextClip karaoke loop with `_burn_subtitles_ffmpeg()` |
| 5 | `services/rendering.py` | Add `_get_whisper_model()` cache, stop cold-loading on every render |
| 6 | `services/rendering.py` | Add `_burn_subtitles_ffmpeg()` using FFmpeg subtitles filter |
| 7 | `routers/clips.py` | Make `approve_clips` non-blocking using `BackgroundTasks` |
| 8 | `routers/clips.py` | Pass thumbnail URLs in `auto_select_clips` scenes_data |
| 9 | `services/ai.py` | Improve scoring prompts with explicit rubric + thumbnail awareness |
| 10 | `config.py` | Document all clip provider options |
| 11 | `schemas.py` | Accept new provider values in `ProjectCreate` |
| 12 | `ClipsStage.tsx` | Show source badge on clip cards |
| 13 | `settings/page.tsx` | Add new provider options to UI selector |

---

## DO NOT CHANGE

- `services/voice.py` — NVIDIA Riva TTS stays as-is
- `models.py` — No schema migrations needed (Clip.source already stores provider name)
- `services/ai.py` — Only the two prompt strings change (select_best_clips, score_clips_for_scene)
- Database — No migration needed, `source` column already supports any string value

---

## TESTING CHECKLIST AFTER CHANGES

1. Set `CLIP_PROVIDER=free` in `.env`, create a project, fetch clips — should get Coverr/Mixkit results with no API keys
2. Set `CLIP_PROVIDER=hybrid` — should get results from all configured sources
3. Approve clips — check that download happens in background, frontend shows "downloading_clips" status
4. Render a video with subtitles — confirm FFmpeg subtitle burn runs (check logs for `_burn_subtitles_ffmpeg`)
5. Render a second video — Whisper model should NOT reload (check logs: "Loading Whisper model" should only appear once per process lifetime)
6. Auto-select clips — verify AI receives thumbnail URLs in the scoring payload