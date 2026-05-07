from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..models import Project, ProjectStatus, Render, Scene, WorkflowStage
from ..schemas import ProjectCreate, ProjectListItem, ProjectOut
from ..utils import project_out
from ..storage import ProjectStorage

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectOut)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)) -> ProjectOut:
    title = payload.idea.strip().splitlines()[0][:80] or "Untitled Project"
    project = Project(
        title=title,
        idea=payload.idea.strip(),
        video_format=payload.video_format,
        video_length=payload.video_length,
        language=payload.language,
        subtitles_enabled=payload.subtitles_enabled,
        subtitle_language=payload.subtitle_language,
        clip_provider=settings.clip_provider,
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
    projects = db.scalars(select(Project).order_by(Project.created_at.desc()).limit(20)).all()
    return [
        ProjectListItem(
            id=item.id,
            title=item.title,
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
    project = db.scalar(
        select(Project)
        .where(Project.id == project_id)
        .options(selectinload(Project.scripts), selectinload(Project.scenes).selectinload(Scene.clips), selectinload(Project.render))
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

