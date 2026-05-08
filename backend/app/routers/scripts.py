from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Project, ProjectStatus, Script, WorkflowStage
from ..schemas import ProjectOut, ScriptUpdate
from ..services.ai import AiServiceError, generate_script, _get_ai_settings
from ..utils import latest_script, list_to_json, project_out, titles_to_json

router = APIRouter(prefix="/projects/{project_id}/script", tags=["script"])


def _project(db: Session, project_id: int) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.post("/generate", response_model=ProjectOut)
def create_script(project_id: int, db: Session = Depends(get_db)) -> ProjectOut:
    project = _project(db, project_id)
    ai_settings = _get_ai_settings()
    provider = ai_settings.get("provider", "ollama")
    try:
        data = generate_script(project.idea, project.video_format, project.language, project.video_length)
    except Exception as exc:
        if isinstance(exc, AiServiceError):
            raise HTTPException(status_code=502, detail=f"AI generation failed: {exc}") from exc
        raise exc

    current = latest_script(project)
    script = Script(
        project_id=project.id,
        version=(current.version + 1) if current else 1,
        video_script=data.get("video_script", ""),
        on_screen_notes=data.get("on_screen_notes", ""),
        title_suggestions=titles_to_json(data.get("title_suggestions", [])),
        description=data.get("description"),
        tags=list_to_json(data.get("tags", [])),
        chapters=list_to_json(data.get("chapters", [])),
        hook_type=data.get("hook_type"),
        estimated_duration=data.get("estimated_duration", ""),
        tone=data.get("tone", ""),
    )
    project.status = ProjectStatus.waiting_review.value
    project.current_stage = WorkflowStage.script.value
    db.add(script)
    db.commit()
    db.refresh(project)
    return project_out(project)


@router.put("", response_model=ProjectOut)
def update_script(project_id: int, payload: ScriptUpdate, db: Session = Depends(get_db)) -> ProjectOut:
    project = _project(db, project_id)
    script = latest_script(project)
    if not script:
        raise HTTPException(status_code=400, detail="Generate a script first")
    if script.approved:
        raise HTTPException(status_code=409, detail="Approved script cannot be edited")
    for key, value in payload.model_dump().items():
        if key == "title_suggestions":
            value = titles_to_json(value)
        elif key in {"tags", "chapters"}:
            value = list_to_json(value)
        setattr(script, key, value)
    db.commit()
    db.refresh(project)
    return project_out(project)


@router.post("/approve", response_model=ProjectOut)
def approve_script(project_id: int, db: Session = Depends(get_db)) -> ProjectOut:
    project = _project(db, project_id)
    script = latest_script(project)
    if not script:
        raise HTTPException(status_code=400, detail="Generate a script first")
    script.approved = True
    project.current_stage = WorkflowStage.scenes.value
    project.status = ProjectStatus.approved.value
    db.commit()
    db.refresh(project)
    return project_out(project)
