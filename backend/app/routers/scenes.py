from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Project, ProjectStatus, Scene, WorkflowStage
from ..schemas import ProjectOut, SceneUpdate
from ..services.ai import AiServiceError, generate_scenes
from ..utils import latest_script, project_out

router = APIRouter(prefix="/projects/{project_id}/scenes", tags=["scenes"])


def _project(db: Session, project_id: int) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.post("/generate", response_model=ProjectOut)
def create_scenes(project_id: int, db: Session = Depends(get_db)) -> ProjectOut:
    project = _project(db, project_id)
    script = latest_script(project)
    if not script or not script.approved:
        raise HTTPException(status_code=409, detail="Approve the script before generating scenes")

    # Use only hook + body — never include CTA in the voiceover source
    script_text = script.video_script

    try:
        scene_items = generate_scenes(script_text, project.video_format, project.language)
    except Exception as exc:
        if isinstance(exc, AiServiceError):
            raise HTTPException(status_code=502, detail=f"Scene generation failed: {exc}") from exc
        raise exc

    project.scenes.clear()
    for item in scene_items:
        duration = float(item["duration_seconds"])
        if duration < 0.5:
            duration = 0.5
        project.scenes.append(
            Scene(
                scene_index=item["scene_index"],
                description=item["description"],
                visual_keyword=item["visual_keyword"],
                duration_seconds=duration,
                voiceover_text=item["voiceover_text"],
            )
        )
    project.current_stage = WorkflowStage.scenes.value
    project.status = ProjectStatus.waiting_review.value
    db.commit()
    db.refresh(project)
    return project_out(project)


@router.put("/{scene_id}", response_model=ProjectOut)
def update_scene(project_id: int, scene_id: int, payload: SceneUpdate, db: Session = Depends(get_db)) -> ProjectOut:
    project = _project(db, project_id)
    scene = db.get(Scene, scene_id)
    if not scene or scene.project_id != project.id:
        raise HTTPException(status_code=404, detail="Scene not found")
    if scene.approved:
        raise HTTPException(status_code=409, detail="Approved scenes cannot be edited")
    for key, value in payload.model_dump().items():
        setattr(scene, key, value)
    db.commit()
    db.refresh(project)
    return project_out(project)


@router.post("/approve", response_model=ProjectOut)
def approve_scenes(project_id: int, db: Session = Depends(get_db)) -> ProjectOut:
    project = _project(db, project_id)
    if not project.scenes:
        raise HTTPException(status_code=400, detail="Generate scenes first")
    for scene in project.scenes:
        scene.approved = True
    project.current_stage = WorkflowStage.clips.value
    project.status = ProjectStatus.approved.value
    db.commit()
    db.refresh(project)
    return project_out(project)
