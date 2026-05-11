from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Settings
from ..schemas import SettingsOut, SettingsUpdate, SettingsWithLabel

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=SettingsWithLabel)
def get_settings(db: Session = Depends(get_db)) -> SettingsWithLabel:
    settings = db.scalar(select(Settings))
    if not settings:
        # Create default settings if they don't exist
        settings = Settings()
        db.add(settings)
        db.commit()
        db.refresh(settings)
    
    labels = {"ollama":"Ollama (Local)","openai":"OpenAI","openrouter":"OpenRouter","vertex":"Google Vertex AI"}
    data = {
        "id": settings.id,
        "llm_provider": settings.llm_provider,
        "ollama_base_url": settings.ollama_base_url,
        "ollama_model": settings.ollama_model,
        "openai_api_key": settings.openai_api_key,
        "openai_model": settings.openai_model,
        "openrouter_api_key": settings.openrouter_api_key,
        "openrouter_model": settings.openrouter_model,
        "vertex_project_id": settings.vertex_project_id,
        "vertex_location": settings.vertex_location,
        "gemini_model": settings.gemini_model,
        "nvidia_api_key": settings.nvidia_api_key,
        "nvidia_model": settings.nvidia_model,
        "nvidia_tts_model": settings.nvidia_tts_model,
        "clip_provider": settings.clip_provider,
        "updated_at": settings.updated_at,
    }
    return SettingsWithLabel(**data, active_provider_label=labels.get(settings.llm_provider, settings.llm_provider))


@router.post("/test")
def test_llm_connection(db: Session = Depends(get_db)) -> dict:
    from ..services.ai import _get_ai_settings, _generate_json
    ai_settings = _get_ai_settings()
    provider = ai_settings.get("provider", "ollama")
    test_schema = {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"]}
    try:
        result = _generate_json("Reply with valid JSON only.", 'Respond with: {"ok": true}', test_schema)
        return {"provider": provider, "success": bool(result.get("ok")), "error": None}
    except Exception as exc:
        return {"provider": provider, "success": False, "error": str(exc)}


@router.put("", response_model=SettingsOut)
def update_settings(payload: SettingsUpdate, db: Session = Depends(get_db)) -> SettingsOut:
    settings = db.scalar(select(Settings))
    if not settings:
        settings = Settings()
        db.add(settings)
    
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(settings, key, value)
    
    db.commit()
    db.refresh(settings)
    return settings
