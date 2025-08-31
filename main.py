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
from core.clients.inngest import inngest_client
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

# Wire up Inngest for async function discovery
# This creates the /api/inngest endpoint that Inngest uses to discover functions
inngest_app = inngest_client.create_fast_api_app(
    app,
    serve_path="/api/inngest",  # Inngest's webhook endpoint
)

# Import workflows to register them with Inngest
# This ensures the decorated functions are discovered
from features.workflows import register_workflow  # noqa: E402

logger.info("Inngest functions registered")


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