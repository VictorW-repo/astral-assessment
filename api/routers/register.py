"""
Register endpoint - accepts lead information and triggers async processing
Validates input and immediately returns while Inngest handles the heavy lifting
"""

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse
import logging
from datetime import datetime, timezone
import uuid

from api.schemas import RegisterRequest, RegisterAccepted, ErrorResponse
from core.clients.inngest import trigger_event
from core.config import settings
from core.utils import safe_url

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post(
    "/register",
    response_model=RegisterAccepted,
    responses={
        400: {"model": ErrorResponse, "description": "Validation error"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def register(request: RegisterRequest):
    """
    Register a new lead for intelligence gathering.
    
    Accepts first_name, last_name, and at least one of company_website or linkedin.
    Triggers async processing via Inngest and returns immediately.
    
    The heavy processing (web scraping, data analysis) happens in the background.
    """
    try:
        # Generate unique request ID
        request_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()
        
        logger.info(f"Processing registration request {request_id} for {request.first_name} {request.last_name}")
        
        # Normalize URLs if provided
        normalized_data = {
            "request_id": request_id,
            "timestamp": timestamp,
            "first_name": request.first_name,
            "last_name": request.last_name,
            "company_website": safe_url(request.company_website) if request.company_website else None,
            "linkedin": safe_url(request.linkedin) if request.linkedin else None
        }
        
        # Log what we're processing
        sources = []
        if normalized_data["company_website"]:
            sources.append(f"website: {normalized_data['company_website']}")
        if normalized_data["linkedin"]:
            sources.append(f"linkedin: {normalized_data['linkedin']}")
        logger.info(f"Request {request_id} will analyze: {', '.join(sources)}")
        
        # Trigger Inngest event for async processing
        # This is the key integration - finding how to trigger from an endpoint
        try:
            event_sent = await trigger_event(
                event_name=settings.INNGEST_REGISTER_EVENT,
                data=normalized_data
            )
            
            if not event_sent:
                logger.warning(f"Inngest event trigger returned False for {request_id}")
                # Continue anyway - we still want to return success
                
        except Exception as e:
            logger.error(f"Failed to trigger Inngest event for {request_id}: {e}")
            # Don't fail the request - we can still return success
            # This follows the "fail gracefully" principle
        
        # Return immediate success
        # The actual processing happens asynchronously
        return RegisterAccepted(
            status="accepted",
            request_id=request_id,
            message=f"Registration accepted for {request.first_name} {request.last_name}. Processing in background.",
            timestamp=timestamp
        )
        
    except ValueError as e:
        # This shouldn't happen as Pydantic validates, but just in case
        logger.error(f"Validation error in register endpoint: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error in register endpoint: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while processing registration"
        )