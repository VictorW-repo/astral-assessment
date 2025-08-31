"""
Inngest client for async function orchestration
This is the tricky part - triggering functions from API endpoints
"""

import logging
from typing import Optional, Dict, Any, Callable
import json
from datetime import datetime

from inngest import Inngest, Event
from inngest.fast_api import serve

from core.config import settings
from core.utils import uid, ts

logger = logging.getLogger(__name__)


# Initialize Inngest client
# This creates the client that will be used to trigger events and register functions
inngest_client = Inngest(
    app_id=settings.INNGEST_APP_ID or "astral-assessment",
    event_key=settings.INNGEST_EVENT_KEY,  # Optional, for production
    is_production=settings.INNGEST_IS_PRODUCTION
)

logger.info(f"Inngest client initialized with app_id: {inngest_client.app_id}")


async def trigger_event(
    event_name: str,
    data: Dict[str, Any],
    event_id: Optional[str] = None,
    ts_override: Optional[str] = None
) -> bool:
    """
    Trigger an Inngest event from the API endpoint.
    This is the key function that the docs don't clearly show how to use.
    
    Args:
        event_name: Name of the event (e.g., "user.registration.requested")
        data: Event data payload
        event_id: Optional event ID (generated if not provided)
        ts_override: Optional timestamp override
    
    Returns:
        bool: True if event was sent successfully
    """
    try:
        # Create event object
        event = Event(
            name=event_name,
            data=data,
            id=event_id or uid(),
            ts=ts_override or datetime.utcnow().timestamp() * 1000  # Inngest expects milliseconds
        )
        
        # Send event to Inngest
        # This is the magic - it queues the event for async processing
        result = inngest_client.send(event)
        
        logger.info(f"Triggered Inngest event: {event_name} with id: {event.id}")
        logger.debug(f"Event data: {json.dumps(data, default=str)[:200]}...")  # Log first 200 chars
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to trigger Inngest event {event_name}: {e}", exc_info=True)
        return False


def create_function(
    function_id: str,
    trigger_event: str,
    retries: int = 3
) -> Callable:
    """
    Create an Inngest function decorator.
    This is used to define background functions that process events.
    
    Args:
        function_id: Unique function identifier
        trigger_event: Event name that triggers this function
        retries: Number of retries on failure
    
    Returns:
        Decorator for the function
    """
    return inngest_client.create_function(
        fn_id=function_id,
        trigger={"event": trigger_event},
        retries=retries
    )


# Register workflow function
# This will be imported by the workflow module
@inngest_client.create_function(
    fn_id="process-registration",
    trigger={"event": settings.INNGEST_REGISTER_EVENT},
    retries=3
)
async def process_registration(event: Event, step):
    """
    Main registration processing function.
    This is triggered by the registration event and handles the async work.
    
    Note: The actual implementation is in features/workflows/register_workflow.py
    This is just the registration with Inngest.
    """
    # Import here to avoid circular dependencies
    from features.workflows.register_workflow import execute_registration_workflow
    
    logger.info(f"Processing registration event: {event.id}")
    logger.debug(f"Event data: {event.data}")
    
    try:
        # Execute the actual workflow
        result = await execute_registration_workflow(event.data, step)
        
        logger.info(f"Successfully processed registration: {event.data.get('request_id')}")
        return result
        
    except Exception as e:
        logger.error(f"Failed to process registration: {e}", exc_info=True)
        raise  # Re-raise to trigger Inngest retry


def create_fast_api_app(app, serve_path: str = "/api/inngest"):
    """
    Create and mount the Inngest FastAPI app.
    This creates the webhook endpoint that Inngest uses to discover and run functions.
    
    This is the critical piece that's not well documented:
    - Inngest needs a webhook endpoint to discover your functions
    - The serve() function creates this endpoint
    - It must be mounted on your FastAPI app
    
    Args:
        app: FastAPI application instance
        serve_path: Path where Inngest webhook will be mounted
    
    Returns:
        The Inngest app (for reference, usually not needed)
    """
    # Get all registered functions
    functions = [
        process_registration,
        # Add other functions here as they're created
    ]
    
    logger.info(f"Registering {len(functions)} Inngest functions at {serve_path}")
    
    # Create the Inngest FastAPI app
    # This creates the /api/inngest endpoint that Inngest polls
    inngest_app = serve(
        inngest_client,
        functions,
        serve_path=serve_path
    )
    
    # The serve() function returns a FastAPI router that needs to be included
    app.include_router(inngest_app)
    
    logger.info(f"Inngest webhook mounted at {serve_path}")
    
    return inngest_app


# Event name constants for consistency
class Events:
    """Event name constants to avoid typos"""
    REGISTRATION_REQUESTED = settings.INNGEST_REGISTER_EVENT
    # Add other events as needed
    WEBSITE_CRAWLED = "website.crawled"
    LINKEDIN_SCRAPED = "linkedin.scraped"
    ANALYSIS_COMPLETED = "analysis.completed"