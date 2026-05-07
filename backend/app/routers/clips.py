from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Clip, Project, ProjectStatus, Scene, WorkflowStage
from ..schemas import ProjectOut
from ..services.ai import AiServiceError, select_best_clips
from ..services.clips import ClipServiceError, download_selected_clip, fetch_clip_options
from ..utils import project_out

router = APIRouter(prefix="/projects/{project_id}/clips", tags=["clips"])


def _project(db: Session, project_id: int) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.post("/fetch", response_model=ProjectOut)
def fetch_clips(project_id: int, db: Session = Depends(get_db)) -> ProjectOut:
    project = _project(db, project_id)
    if not project.scenes or not all(scene.approved for scene in project.scenes):
        raise HTTPException(status_code=409, detail="Approve scenes before fetching clips")

    try:
        fetched_by_scene: dict[int, list[dict]] = {}
        missing_scenes: list[int] = []
        for scene in project.scenes:
            items = fetch_clip_options(scene, project)
            if items:
                fetched_by_scene[scene.id] = items
            elif not scene.clips:
                missing_scenes.append(scene.scene_index)
    except ClipServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if missing_scenes:
        raise HTTPException(
            status_code=502,
            detail=f"No clip options found for scenes: {', '.join(map(str, missing_scenes))}. Try improving the visual keywords.",
        )

    for scene in project.scenes:
        items = fetched_by_scene.get(scene.id)
        if not items:
            continue
        scene.clips.clear()
        for item in items:
            scene.clips.append(Clip(**item))

    project.current_stage = WorkflowStage.clips.value
    project.status = ProjectStatus.waiting_review.value
    db.commit()
    db.refresh(project)
    return project_out(project)


@router.post("/{scene_id}/select/{clip_id}", response_model=ProjectOut)
def select_clip(project_id: int, scene_id: int, clip_id: int, db: Session = Depends(get_db)) -> ProjectOut:
    project = _project(db, project_id)
    scene = db.get(Scene, scene_id)
    if not scene or scene.project_id != project.id:
        raise HTTPException(status_code=404, detail="Scene not found")
    clip = db.get(Clip, clip_id)
    if not clip or clip.scene_id != scene.id:
        raise HTTPException(status_code=404, detail="Clip not found")
    for option in scene.clips:
        option.selected = option.id == clip.id
    db.commit()
    db.refresh(project)
    return project_out(project)


@router.post("/approve", response_model=ProjectOut)
def approve_clips(project_id: int, db: Session = Depends(get_db)) -> ProjectOut:
    project = _project(db, project_id)
    if not project.scenes:
        raise HTTPException(status_code=400, detail="No scenes available")
    for scene in project.scenes:
        selected = next((clip for clip in scene.clips if clip.selected), None)
        if not selected:
            raise HTTPException(status_code=409, detail=f"Scene {scene.scene_index} needs one selected clip")
        if not selected.local_path:
            try:
                selected.local_path = download_selected_clip(project.id, selected)
            except ClipServiceError as exc:
                raise HTTPException(status_code=502, detail=f"Scene {scene.scene_index}: {exc}") from exc

    project.current_stage = WorkflowStage.voiceover.value
    project.status = ProjectStatus.approved.value
    db.commit()
    db.refresh(project)
    return project_out(project)


@router.post("/auto-select", response_model=ProjectOut)
def auto_select_clips(project_id: int, db: Session = Depends(get_db)) -> ProjectOut:
    project = _project(db, project_id)
    if not project.scenes:
        raise HTTPException(status_code=400, detail="No scenes available")

    # Build input for AI
    scenes_data = []
    for scene in project.scenes:
        if not scene.clips:
            continue
        candidates = [{"clip_id": c.id, "name": c.name} for c in scene.clips]
        scenes_data.append({
            "scene_id": scene.id,
            "description": scene.description,
            "candidates": candidates
        })

    if not scenes_data:
        raise HTTPException(status_code=400, detail="No clips fetched yet")

    try:
        selections = select_best_clips(scenes_data)
    except AiServiceError as exc:
        raise HTTPException(status_code=502, detail=f"AI selection failed: {exc}") from exc

    # Apply selections
    for selection in selections:
        scene_id = selection["scene_id"]
        clip_id = selection["selected_clip_id"]
        scene = db.get(Scene, scene_id)
        if scene and scene.project_id == project.id:
            for clip in scene.clips:
                clip.selected = (clip.id == clip_id)

    db.commit()
    db.refresh(project)
    return project_out(project)
