from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Settings
from ..schemas import SettingsOut, SettingsUpdate

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=SettingsOut)
def get_settings(db: Session = Depends(get_db)) -> SettingsOut:
    settings = db.scalar(select(Settings))
    if not settings:
        # Create default settings if they don't exist
        settings = Settings()
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


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
