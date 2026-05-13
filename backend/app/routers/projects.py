
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..config import settings
from ..database import get_db
from ..models import Project, ProjectStatus, Render, Scene, WorkflowStage
from ..schemas import ProjectCreate, ProjectListItem, ProjectOut
from ..utils import project_out
from ..storage import ProjectStorage

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectOut)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)) -> ProjectOut:
    idea_clean = payload.idea.strip()
    title = idea_clean.splitlines()[0][:80] or "Untitled Project"

    # Ensure Settings row exists and use DB settings clip_provider as default
    from ..models import Settings as SettingsModel
    db_settings = db.scalar(select(SettingsModel))
    if not db_settings:
        db_settings = SettingsModel()
        db.add(db_settings)
        db.commit()
        db.refresh(db_settings)
    
    default_clip_provider = db_settings.clip_provider if db_settings else settings.clip_provider

    project = Project(
        title=title,
        idea=idea_clean,
        category=payload.category,
        video_format=payload.video_format,
        video_length=payload.video_length,
        language=payload.language,
        subtitles_enabled=payload.subtitles_enabled,
        subtitle_language=payload.subtitle_language,
        clip_provider=payload.clip_provider or default_clip_provider,
        current_stage=WorkflowStage.script.value,
        status=ProjectStatus.draft.value,
    )
    project.render = Render()
    db.add(project)
    db.commit()
    db.refresh(project)
    return project_out(project)


@router.get("", response_model=list[ProjectListItem])
def list_projects(db: Session = Depends(get_db)) -> list[ProjectListItem]:
    # Use index-friendly query with limit to avoid loading all projects
    projects = db.scalars(
        select(Project)
        .order_by(Project.created_at.desc())
        .limit(20)
    ).all()
    return [
        ProjectListItem(
            id=item.id,
            title=item.title,
            category=item.category,
            video_format=item.video_format,
            video_length=item.video_length,
            language=item.language,
            subtitles_enabled=item.subtitles_enabled,
            subtitle_language=item.subtitle_language,
            clip_provider=item.clip_provider,
            current_stage=item.current_stage,
            status=item.status,
            created_at=item.created_at,
        )
        for item in projects
    ]


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: int, db: Session = Depends(get_db)) -> ProjectOut:
    # Eager load all relationships to prevent N+1 queries
    project = db.scalar(
        select(Project)
        .where(Project.id == project_id)
        .options(
            selectinload(Project.scripts),
            selectinload(Project.scenes).selectinload(Scene.clips),
            selectinload(Project.render)
        )
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project_out(project)


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: int, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Delete from DB
    db.delete(project)
    db.commit()
    
    # Clear isolated project assets gracefully
    ProjectStorage(project_id).clear_project_assets()


@router.post("/{project_id}/jump/{stage}", response_model=ProjectOut)
def jump_to_stage(project_id: int, stage: WorkflowStage, db: Session = Depends(get_db)) -> ProjectOut:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    project.current_stage = stage.value
    
    if stage == WorkflowStage.script:
        project.status = ProjectStatus.draft.value
        for s in project.scripts:
            s.approved = False
    elif stage == WorkflowStage.scenes:
        project.status = ProjectStatus.waiting_review.value
        for s in project.scenes:
            s.approved = False
    elif stage == WorkflowStage.clips or stage == WorkflowStage.image_upload:
        if project.video_format == "image_story":
            project.current_stage = WorkflowStage.image_upload.value
            project.status = ProjectStatus.waiting_images.value
        else:
            project.current_stage = WorkflowStage.clips.value
            project.status = ProjectStatus.waiting_review.value
    elif stage == WorkflowStage.voiceover:
        project.status = ProjectStatus.approved.value
    elif stage == WorkflowStage.render:
        project.status = ProjectStatus.approved.value

    db.commit()
    db.refresh(project)
    return project_out(project)

