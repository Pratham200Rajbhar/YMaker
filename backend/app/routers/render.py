from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Project, ProjectStatus
from ..schemas import ProjectOut
from ..services.rendering import render_project
from ..utils import project_out

router = APIRouter(prefix="/projects/{project_id}/render", tags=["render"])


def _project(db: Session, project_id: int) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.post("/start", response_model=ProjectOut)
def start(project_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)) -> ProjectOut:
    project = _project(db, project_id)
    if not project.render or not project.render.voiceover_approved:
        raise HTTPException(status_code=400, detail="Voiceover must be generated and approved before rendering.")
    project.render.render_status = "queued"
    project.render.error_message = None
    project.status = ProjectStatus.rendering.value
    db.commit()
    background_tasks.add_task(render_project, project.id)
    db.refresh(project)
    return project_out(project)


@router.get("", response_model=ProjectOut)
def status(project_id: int, db: Session = Depends(get_db)) -> ProjectOut:
    return project_out(_project(db, project_id))
