import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pythonjsonlogger import jsonlogger

from .config import STORAGE_DIR, LOG_FILE, ensure_storage_dirs, settings
from .database import init_db
from .routers import (
    ai,
    clips,
    projects,
    render,
    scenes,
    scripts,
    voice,
    settings as settings_router,
    categories,
    logs,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown."""
    ensure_storage_dirs()
    setup_logging()
    logger.info("Starting up %s...", settings.app_name)
    init_db()
    yield
    logger.info("Shutting down %s...", settings.app_name)


def setup_logging():
    """Configure structured JSON logging."""
    log_handler = logging.FileHandler(str(LOG_FILE))
    formatter = jsonlogger.JsonFormatter(
        "%(asctime)s %(name)s %(levelname)s %(message)s",
        rename_fields={"asctime": "timestamp", "levelname": "level"},
    )
    log_handler.setFormatter(formatter)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(log_handler)
    
    # Add a console handler for development
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    root_logger.addHandler(console_handler)

    # Specific configuration for our app logger
    app_logger = logging.getLogger("app")
    app_logger.setLevel(logging.DEBUG)
    
    # Prevent duplicate logs in console if root already has it
    app_logger.propagate = True


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, lifespan=lifespan)

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin, "http://127.0.0.1:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Request logging middleware
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start = time.time()
        
        # Capture request details
        path = request.url.path
        method = request.method
        client_ip = request.client.host if request.client else "unknown"
        
        try:
            response = await call_next(request)
            duration = (time.time() - start) * 1000
            
            log_data = {
                "method": method,
                "path": path,
                "status_code": response.status_code,
                "duration_ms": round(duration, 2),
                "client_ip": client_ip,
            }
            
            if response.status_code >= 400:
                logger.error(
                    "Request failed: %s %s -> %s",
                    method,
                    path,
                    response.status_code,
                    extra=log_data,
                )
            else:
                logger.info(
                    "Request: %s %s -> %s",
                    method,
                    path,
                    response.status_code,
                    extra=log_data,
                )

            return response
        except Exception as e:
            duration = (time.time() - start) * 1000
            logger.exception(
                "Unhandled exception during %s %s",
                method,
                path,
                extra={
                    "method": method,
                    "path": path,
                    "duration_ms": round(duration, 2),
                    "client_ip": client_ip,
                    "error": str(e),
                },
            )
            raise

    # Static files
    app.mount("/media", StaticFiles(directory=STORAGE_DIR), name="media")

    # Routers
    app.include_router(projects.router)
    app.include_router(ai.router)
    app.include_router(scripts.router)
    app.include_router(scenes.router)
    app.include_router(clips.router)
    app.include_router(voice.router)
    app.include_router(render.router)
    app.include_router(settings_router.router)
    app.include_router(categories.router)
    app.include_router(logs.router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "app": settings.app_name}

    return app


app = create_app()
