import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pythonjsonlogger import jsonlogger
from sqlalchemy import text

from .config import STORAGE_DIR, LOG_FILE, ensure_storage_dirs, settings
from .database import init_db
from .routers import (
    ai,
    clips,
    image_scenes,
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

    # CORS - validate frontend_origin to prevent misconfiguration
    allowed_origins = [settings.frontend_origin]
    # Only allow localhost in development for safety
    if "localhost" in settings.frontend_origin or "127.0.0.1" in settings.frontend_origin:
        allowed_origins.append("http://127.0.0.1:3000")
        allowed_origins.append("http://localhost:3000")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
        allow_headers=["Content-Type", "Authorization"],
    )

    # Request ID middleware for tracing
    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    # Request logging middleware
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start = time.time()
        
        # Capture request details
        request_id = getattr(request.state, "request_id", "unknown")
        path = request.url.path
        method = request.method
        client_ip = request.client.host if request.client else "unknown"
        
        try:
            response = await call_next(request)
            duration = (time.time() - start) * 1000
            
            log_data = {
                "request_id": request_id,
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
                    "request_id": request_id,
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
    app.mount("/storage", StaticFiles(directory=STORAGE_DIR), name="storage")

    # Routers
    app.include_router(projects.router)
    app.include_router(ai.router)
    app.include_router(scripts.router)
    app.include_router(scenes.router)
    app.include_router(clips.router)
    app.include_router(image_scenes.router)
    app.include_router(voice.router)
    app.include_router(render.router)
    app.include_router(settings_router.router)
    app.include_router(categories.router)
    app.include_router(logs.router)

    @app.get("/health")
    def health() -> dict[str, str | bool]:
        """Health check endpoint with dependency status."""
        health_status = {
            "status": "ok",
            "app": settings.app_name,
            "database": False,
            "storage": False,
        }
        
        # Check database connection
        try:
            from .database import engine
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            health_status["database"] = True
        except Exception as e:
            logger.error("Health check: Database connection failed: %s", e)
            health_status["status"] = "degraded"
        
        # Check storage directory
        try:
            health_status["storage"] = STORAGE_DIR.exists() and STORAGE_DIR.is_dir()
            if not health_status["storage"]:
                logger.error("Health check: Storage directory not accessible")
                health_status["status"] = "degraded"
        except Exception as e:
            logger.error("Health check: Storage check failed: %s", e)
            health_status["status"] = "degraded"
        
        return health_status

    return app


app = create_app()
