from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import STORAGE_DIR, ensure_storage_dirs, settings
from .database import init_db
from .routers import ai, clips, projects, render, scenes, scripts, voice


def create_app() -> FastAPI:
    ensure_storage_dirs()
    init_db()

    app = FastAPI(title=settings.app_name)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin, "http://127.0.0.1:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.mount("/media", StaticFiles(directory=STORAGE_DIR), name="media")
    app.include_router(projects.router)
    app.include_router(ai.router)
    app.include_router(scripts.router)
    app.include_router(scenes.router)
    app.include_router(clips.router)
    app.include_router(voice.router)
    app.include_router(render.router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
