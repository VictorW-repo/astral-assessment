"""
Health check endpoints for application monitoring
Following astral's pattern of having both basic and detailed health checks
"""

from fastapi import APIRouter, Response
from datetime import datetime, timezone
import platform
import sys
import os
from pathlib import Path
import psutil
import logging

from core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("")
async def health_check(response: Response):
    """
    Basic health endpoint - returns minimal status info
    Used for quick liveness checks by load balancers
    """
    try:
        # Basic check that core systems are responsive
        status = "healthy"
        response.status_code = 200
        
        return {
            "status": status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service": "astral-assessment"
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        response.status_code = 503
        return {
            "status": "unhealthy",
            "error": str(e)
        }


@router.get("/detailed")
async def health_check_detailed():
    """
    Detailed health endpoint - returns comprehensive system information
    This is a habit from astral's engineering practices
    """
    try:
        # Get process info
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        
        # Count output files
        output_dir = Path(settings.OUTPUT_DIR)
        output_files = len(list(output_dir.glob("analysis_*.json"))) if output_dir.exists() else 0
        
        # Check integrations
        integrations = {
            "inngest": {
                "configured": bool(settings.INNGEST_APP_ID),
                "app_id": settings.INNGEST_APP_ID or "not_configured",
                "event_key": settings.INNGEST_EVENT_KEY or "not_configured"
            },
            "firecrawl": {
                "configured": bool(settings.FIRECRAWL_API_KEY),
                "api_url": settings.FIRECRAWL_API_URL,
                "has_key": bool(settings.FIRECRAWL_API_KEY)
            }
        }
        
        return {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service": "astral-assessment",
            "version": "1.0.0",
            "environment": settings.ENVIRONMENT,
            "system": {
                "platform": platform.platform(),
                "python_version": sys.version,
                "processor": platform.processor() or "unknown",
                "cpu_count": os.cpu_count()
            },
            "process": {
                "pid": os.getpid(),
                "memory_usage_mb": round(memory_info.rss / 1024 / 1024, 2),
                "cpu_percent": process.cpu_percent(),
                "threads": process.num_threads(),
                "uptime_seconds": round(datetime.now().timestamp() - process.create_time())
            },
            "application": {
                "output_files_count": output_files,
                "output_directory": str(output_dir),
                "log_level": settings.LOG_LEVEL
            },
            "integrations": integrations,
            "philosophy": "wars are won with logistics and propaganda"
        }
        
    except Exception as e:
        logger.error(f"Detailed health check failed: {e}")
        return {
            "status": "unhealthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error": str(e),
            "error_type": type(e).__name__
        }