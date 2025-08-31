"""
Astral Assessment - Main FastAPI Application
Entry point that wires up routers, middleware, and Inngest integration
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
from pathlib import Path

from api.routers import health, register
from api.middleware import RequestTimingMiddleware
from core.config import settings
from core.utils import ensure_dir

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifecycle - startup and shutdown events
    """
    # Startup
    logger.info("Starting Astral Assessment API")
    
    # Ensure output directory exists
    ensure_dir(settings.OUTPUT_DIR)
    
    # Log configuration status
    logger.info(f"Inngest configured: {settings.INNGEST_APP_ID is not None}")
    logger.info(f"Firecrawl configured: {settings.FIRECRAWL_API_KEY is not None}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Astral Assessment API")


# Initialize FastAPI app
app = FastAPI(
    title="Astral Assessment API",
    description="MVP for highly tailored lead intelligence pipeline",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware (configured for development)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add custom request timing middleware
app.add_middleware(RequestTimingMiddleware)

# Mount routers
app.include_router(health.router, prefix="/health", tags=["health"])
app.include_router(register.router, tags=["register"])

# Import workflows to ensure functions are registered
from features.workflows import register_workflow  # noqa: E402

# Simplified Inngest integration
# Since the exact API is unclear, we'll create a simple webhook endpoint
# that can be configured with Inngest's dashboard or CLI
logger.info("Note: Inngest integration simplified - configure webhook in Inngest dashboard")
logger.info("Webhook URL: http://localhost:8000/api/inngest")

# Create a simple Inngest webhook endpoint
@app.post("/api/inngest", include_in_schema=False)
async def inngest_webhook(request: dict):
    """
    Inngest webhook endpoint for receiving events.
    In production, this would validate signatures and process events.
    For the assessment, we'll keep it simple.
    """
    # Import here to avoid circular imports
    from core.clients.inngest import process_registration
    from inngest import Event
    
    try:
        # In a real implementation, we'd parse the Inngest event format
        # For now, just log that we received something
        logger.info(f"Received Inngest webhook call: {request}")
        
        # If it looks like a registration event, process it
        if request.get("name") == settings.INNGEST_REGISTER_EVENT:
            event = Event(
                name=request.get("name"),
                data=request.get("data", {}),
                id=request.get("id", "unknown")
            )
            # Note: In production, this would be properly async with Inngest's step functions
            # For the assessment, we'll process synchronously
            from features.workflows.register_workflow import execute_registration_workflow_sync
            import asyncio
            result = asyncio.create_task(
                execute_registration_workflow_sync(event.data)
            )
            return {"status": "accepted", "message": "Event queued for processing"}
        
        return {"status": "received"}
        
    except Exception as e:
        logger.error(f"Error processing Inngest webhook: {e}")
        return {"status": "error", "message": str(e)}


@app.get("/", tags=["root"])
async def root():
    """
    Root endpoint - provides basic API information
    """
    return {
        "service": "Astral Assessment API",
        "status": "operational",
        "endpoints": {
            "health": "/health",
            "health_detailed": "/health/detailed",
            "register": "/register",
            "inngest": "/api/inngest",
            "docs": "/docs"
        },
        "philosophy": "wars are won with logistics and propaganda"
    }


if __name__ == "__main__":
    import uvicorn
    
    # Run with uvicorn for development
    # In production, use: uvicorn main:app --host 0.0.0.0 --port 8000
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )