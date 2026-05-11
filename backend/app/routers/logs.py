"""Router for receiving logs from the frontend."""

import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/logs", tags=["logs"])
logger = logging.getLogger("frontend")


class LogEntry(BaseModel):
    """A single log entry from the frontend."""
    level: str
    message: str
    timestamp: str
    metadata: Optional[Dict[str, Any]] = None


class LogRequest(BaseModel):
    """A collection of log entries from the frontend."""
    logs: List[LogEntry]


@router.post("")
async def receive_logs(payload: LogRequest):
    """Receive logs from the frontend and store them in the backend logs."""
    for entry in payload.logs:
        # We use a specific logger name "frontend" to distinguish them
        log_msg = f"[{entry.level.upper()}] {entry.message}"
        extra = {
            "frontend_timestamp": entry.timestamp,
            "source": "frontend",
            **(entry.metadata or {})
        }

        if entry.level.lower() == "error":
            logger.error(log_msg, extra=extra)
        elif entry.level.lower() == "warn":
            logger.warning(log_msg, extra=extra)
        else:
            logger.info(log_msg, extra=extra)

    return {"status": "ok", "received": len(payload.logs)}
