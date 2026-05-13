import io
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from PIL import Image

from ..database import get_db
from ..models import Project, ProjectStatus, Scene, WorkflowStage
import requests
from ..schemas import ProjectOut, SceneImagePromptUpdate, SceneOut, SceneVoiceAssign, SceneImageUrlUpload
from ..services.ai import AiServiceError, generate_text
from ..storage import ProjectStorage
from ..utils import project_out, scene_out

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/projects/{project_id}/image-scenes", tags=["image_scenes"])

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB


def _project(db: Session, project_id: int) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.post("/generate-prompts", response_model=ProjectOut)
def generate_prompts(project_id: int, db: Session = Depends(get_db)) -> ProjectOut:
    project = _project(db, project_id)
    if project.video_format != "image_story":
        raise HTTPException(status_code=400, detail="This endpoint is only for image_story projects")

    scenes = sorted(project.scenes, key=lambda s: s.scene_index)
    system_instruction = (
        "You are a master cinematic prompt engineer for high-end AI image generators like Midjourney v6, DALL-E 3, and SDXL. "
        "Your task is to create hyper-detailed, evocative, and visually stunning prompts that capture every nuance of a scene. "
        "Every prompt MUST provide extreme detail on: \n"
        "1. ENVIRONMENT: Atmospheric depth, weather, precise location details, architectural elements, and background objects.\n"
        "2. CHARACTERS: Specific clothing (texture, material, layering, color), intricate facial expressions (micro-emotions), "
        "hair texture, eye color, skin details (pores, freckles), and dynamic posture.\n"
        "3. LIGHTING & COLOR: Source of light (golden hour, neon, moonlight), cinematic lighting (rim light, volumetric fog, "
        "chiaroscuro), and a specific color palette (teal and orange, monochrome, vibrant pastels).\n"
        "4. CAMERA & COMPOSITION: Precise camera angle (dutch tilt, extreme close-up, wide panoramic), lens characteristics "
        "(bokeh, 35mm film grain, anamorphic flare), and composition (centered, leading lines).\n"
        "5. STYLE: The specific artistic medium requested (e.g., hyper-realistic photography, intricate digital oil painting, "
        "Ghibli-style anime, dark fantasy concept art).\n"
        "6. CONSISTENCY: Maintain character visual identity (facial features, hair, age) and environmental consistency across prompts if they share the same subject.\n"
        "Output ONLY the prompt text. No preamble, no introductory text, no quotation marks."
    )

    for scene in scenes:
        user_message = (
            f"OVERALL PROJECT THEME: {project.idea}\n"
            f"CHOSEN ART STYLE: {project.category}\n"
            f"SCENE CONTEXT: {scene.description}\n"
            f"VOICEOVER DIALOGUE: {scene.voiceover_text}\n\n"
            "TASK: Generate a single, comprehensive, and ultra-detailed image generation prompt for this specific scene. "
            "The prompt should be wordy and descriptive, focusing heavily on the character's unique clothing, "
            "their specific facial expression reflecting the mood of the voiceover, and the rich textures of the environment. "
            "Ensure the visual details remain consistent with the overall project theme."
        )
        try:
            prompt_text = generate_text(system_instruction, user_message)
        except AiServiceError as exc:
            logger.error("Failed to generate image prompt for scene %d: %s", scene.scene_index, exc)
            raise HTTPException(status_code=502, detail=f"AI prompt generation failed for scene {scene.scene_index}: {exc}") from exc

        scene.image_prompt = prompt_text
        scene.image_prompt_approved = False

    project.current_stage = WorkflowStage.image_upload.value
    project.status = ProjectStatus.waiting_images.value
    db.commit()
    db.refresh(project)
    return project_out(project)


@router.put("/{scene_id}/prompt", response_model=SceneOut)
def update_prompt(project_id: int, scene_id: int, body: SceneImagePromptUpdate, db: Session = Depends(get_db)) -> SceneOut:
    project = _project(db, project_id)
    scene = db.get(Scene, scene_id)
    if not scene or scene.project_id != project.id:
        raise HTTPException(status_code=404, detail="Scene not found")
    scene.image_prompt = body.image_prompt
    scene.image_prompt_approved = body.image_prompt_approved
    db.commit()
    db.refresh(scene)
    return scene_out(scene)


def _save_scene_image(project: Project, scene: Scene, contents: bytes, content_type: str, db: Session) -> SceneOut:
    if content_type not in ALLOWED_CONTENT_TYPES:
        # Try to guess from content if it's generic
        if content_type == "application/octet-stream" or not content_type:
             try:
                 img = Image.open(io.BytesIO(contents))
                 if img.format == "JPEG": content_type = "image/jpeg"
                 elif img.format == "PNG": content_type = "image/png"
                 elif img.format == "WEBP": content_type = "image/webp"
                 else: raise HTTPException(status_code=422, detail=f"Unsupported image format: {img.format}")
             except Exception:
                 raise HTTPException(status_code=422, detail=f"Invalid or unsupported image format.")
        else:
            raise HTTPException(status_code=422, detail=f"Invalid file type: {content_type}. Only jpeg, png, webp allowed.")

    ext_map = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
    extension = ext_map.get(content_type, ".jpg")

    storage = ProjectStorage(project.id)
    images_dir = storage.get_images_dir()
    file_path = images_dir / f"scene_{scene.scene_index}{extension}"

    try:
        # Validate file size
        if len(contents) > MAX_IMAGE_SIZE:
            raise HTTPException(status_code=413, detail=f"File too large. Maximum size is {MAX_IMAGE_SIZE // (1024*1024)}MB.")
        if len(contents) == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")
        
        # Validate actual image content
        try:
            img = Image.open(io.BytesIO(contents))
            img.verify()
            img = Image.open(io.BytesIO(contents))
            if img.width < 64 or img.height < 64:
                raise HTTPException(status_code=422, detail="Image dimensions too small (minimum 64x64).")
        except HTTPException:
            raise
        except Exception as img_exc:
            # Log first 32 bytes to see what we got
            prefix = contents[:32].hex()
            logger.error("Failed to identify image. Size: %d bytes, Prefix: %s, Error: %s", len(contents), prefix, img_exc)
            raise HTTPException(
                status_code=422, 
                detail=f"Invalid image format. If you dragged this from a website, try saving it to your computer first, then dragging the file here."
            ) from img_exc
        
        file_path.write_bytes(contents)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to save scene image")
        raise HTTPException(status_code=500, detail=f"Internal server error while saving image: {exc}") from exc

    scene.uploaded_image_path = str(file_path)
    scene.image_ready = True
    db.commit()
    db.refresh(scene)

    # Check if all scenes now have images ready
    all_ready = all(s.image_ready for s in project.scenes)
    if all_ready:
        project.status = ProjectStatus.approved.value
        db.commit()
        db.refresh(project)

    return scene_out(scene)


@router.post("/{scene_id}/upload-image", response_model=SceneOut)
def upload_image(project_id: int, scene_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)) -> SceneOut:
    project = _project(db, project_id)
    scene = db.get(Scene, scene_id)
    if not scene or scene.project_id != project.id:
        raise HTTPException(status_code=404, detail="Scene not found")

    contents = file.file.read()
    content_type = file.content_type or ""
    try:
        return _save_scene_image(project, scene, contents, content_type, db)
    finally:
        file.file.close()


@router.post("/{scene_id}/upload-image-by-url", response_model=SceneOut)
def upload_image_by_url(project_id: int, scene_id: int, body: SceneImageUrlUpload, db: Session = Depends(get_db)) -> SceneOut:
    project = _project(db, project_id)
    scene = db.get(Scene, scene_id)
    if not scene or scene.project_id != project.id:
        raise HTTPException(status_code=404, detail="Scene not found")

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        response = requests.get(body.url, headers=headers, timeout=30)
        response.raise_for_status()
        contents = response.content
        content_type = response.headers.get("Content-Type", "image/jpeg")
    except Exception as exc:
        logger.error("Failed to download image from URL %s: %s", body.url, exc)
        detail = "Failed to download image from web. Access was denied or the link is private."
        if isinstance(exc, requests.HTTPError) and exc.response.status_code == 403:
            detail = "This website blocks direct image dragging. Try saving the image to your computer first, then drag it here."
        raise HTTPException(status_code=400, detail=detail)

    return _save_scene_image(project, scene, contents, content_type, db)


@router.delete("/{scene_id}/image", response_model=SceneOut)
def delete_image(project_id: int, scene_id: int, db: Session = Depends(get_db)) -> SceneOut:
    project = _project(db, project_id)
    scene = db.get(Scene, scene_id)
    if not scene or scene.project_id != project.id:
        raise HTTPException(status_code=404, detail="Scene not found")

    if scene.uploaded_image_path:
        Path(scene.uploaded_image_path).unlink(missing_ok=True)

    scene.uploaded_image_path = None
    scene.image_ready = False

    if project.status == ProjectStatus.approved.value:
        project.status = ProjectStatus.waiting_images.value

    db.commit()
    db.refresh(scene)
    return scene_out(scene)


@router.get("/progress")
def get_progress(project_id: int, db: Session = Depends(get_db)) -> dict:
    project = _project(db, project_id)
    scenes = sorted(project.scenes, key=lambda s: s.scene_index)
    total = len(scenes)
    ready = sum(1 for s in scenes if s.image_ready)
    return {
        "total_scenes": total,
        "images_ready": ready,
        "all_ready": ready == total and total > 0,
        "scenes": [
            {
                "scene_id": s.id,
                "scene_index": s.scene_index,
                "image_ready": s.image_ready,
                "image_prompt": s.image_prompt,
                "image_prompt_approved": s.image_prompt_approved,
            }
            for s in scenes
        ],
    }


@router.put("/{scene_id}/assign-voice", response_model=SceneOut)
def assign_voice(project_id: int, scene_id: int, body: SceneVoiceAssign, db: Session = Depends(get_db)) -> SceneOut:
    project = _project(db, project_id)
    scene = db.get(Scene, scene_id)
    if not scene or scene.project_id != project.id:
        raise HTTPException(status_code=404, detail="Scene not found")
    scene.character_voice = body.character_voice
    db.commit()
    db.refresh(scene)
    return scene_out(scene)


@router.post("/approve-images", response_model=ProjectOut)
def approve_images(project_id: int, db: Session = Depends(get_db)) -> ProjectOut:
    project = _project(db, project_id)
    if project.video_format != "image_story":
        raise HTTPException(status_code=400, detail="This endpoint is only for image_story projects")
    missing = [f"Scene {s.scene_index}" for s in project.scenes if not s.image_ready]
    if missing:
        raise HTTPException(status_code=400, detail="Not all scenes have images ready: " + ", ".join(missing))
    project.current_stage = WorkflowStage.voiceover.value
    project.status = ProjectStatus.approved.value
    db.commit()
    db.refresh(project)
    return project_out(project)
