import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Project, WorkflowStage
from ..schemas import ProjectOut, VoiceGenerate
from ..services.voice import generate_voiceover, VoiceServiceError
from ..utils import project_out

router = APIRouter(prefix="/projects", tags=["voiceover"])
logger = logging.getLogger(__name__)

@router.post("/{project_id}/voiceover/generate", response_model=ProjectOut)
def generate_project_voiceover(
    project_id: int,
    req: VoiceGenerate,
    db: Session = Depends(get_db)
) -> ProjectOut:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        generate_voiceover(project, req.voice_name, db)
        return project_out(project)
    except VoiceServiceError as exc:
        logger.error("Voiceover generation failed: %s", str(exc))
        raise HTTPException(status_code=500, detail=str(exc))

@router.post("/{project_id}/voiceover/approve", response_model=ProjectOut)
def approve_voiceover(project_id: int, db: Session = Depends(get_db)) -> ProjectOut:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not project.render or not project.render.voiceover_path:
        raise HTTPException(status_code=400, detail="No voiceover generated yet")

    project.render.voiceover_approved = True
    project.current_stage = WorkflowStage.render.value
    db.commit()
    return project_out(project)

@router.get("/{project_id}/voices")
def list_voices():
    # Returning a fixed list of voices supported by NVIDIA Magpie TTS
    return [
        {"id": "Magpie-Multilingual.HI-IN.Aria", "name": "Aria (Hindi/Multilingual)"},
        {"id": "Magpie-Multilingual.HI-IN.John", "name": "John (Hindi/Multilingual)"},
        {"id": "Magpie-Multilingual.HI-IN.Sofia", "name": "Sofia (Hindi/Multilingual)"},
        {"id": "Magpie-Multilingual.HI-IN.Jason", "name": "Jason (Hindi/Multilingual)"},
        {"id": "Magpie-Multilingual.HI-IN.Leo", "name": "Leo (Hindi/Multilingual)"},
    ]
