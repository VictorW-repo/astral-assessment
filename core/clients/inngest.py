"""
Inngest client for async function orchestration
This is the tricky part - triggering functions from API endpoints
"""

import logging
from typing import Optional, Dict, Any
import json
import hmac
import hashlib
from datetime import datetime

from inngest import Inngest, Event

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
    correlation_id = event_id or uid()
    
    try:
        # Create event object
        event = Event(
            name=event_name,
            data=data,
            id=correlation_id,
            ts=ts_override or datetime.utcnow().timestamp() * 1000  # Inngest expects milliseconds
        )
        
        # Send event to Inngest
        # This is the magic - it queues the event for async processing
        result = inngest_client.send(event)
        
        logger.info(f"Triggered Inngest event: {event_name} with correlation_id: {correlation_id}")
        logger.debug(f"Event data: {json.dumps(data, default=str)[:200]}...")  # Log first 200 chars
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to trigger Inngest event {event_name} (correlation_id: {correlation_id}): {e}", exc_info=True)
        return False


def validate_webhook_signature(
    payload: bytes,
    signature: Optional[str],
    signing_key: Optional[str]
) -> bool:
    """
    Validate Inngest webhook signature for security.
    
    Args:
        payload: Raw webhook payload bytes
        signature: Signature from Inngest-Signature header
        signing_key: Inngest signing key from configuration
    
    Returns:
        bool: True if signature is valid or validation disabled
    """
    # Skip validation if no signing key configured (development mode)
    if not signing_key:
        logger.debug("Webhook signature validation skipped - no signing key configured")
        return True
    
    # Skip validation if no signature provided
    if not signature:
        logger.warning("Webhook signature validation failed - no signature header")
        return False
    
    try:
        # Parse signature (format: "s=<signature>")
        if not signature.startswith("s="):
            logger.warning("Invalid signature format - expected 's=<signature>'")
            return False
        
        provided_signature = signature[2:]  # Remove "s=" prefix
        
        # Calculate expected signature
        expected_signature = hmac.new(
            signing_key.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        # Compare signatures (constant-time comparison)
        is_valid = hmac.compare_digest(provided_signature, expected_signature)
        
        if not is_valid:
            logger.warning("Webhook signature validation failed - signature mismatch")
        else:
            logger.debug("Webhook signature validation passed")
            
        return is_valid
        
    except Exception as e:
        logger.error(f"Webhook signature validation error: {e}")
        return False


# Register workflow function
# This will be imported by main.py for serving
@inngest_client.create_function(
    fn_id="process-registration",
    trigger={"event": settings.INNGEST_REGISTER_EVENT},
    retries=3
)
async def process_registration(event: Event, step):
    """
    Main registration processing function.
    This is triggered by the registration event and handles the async work.
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


# Event name constants for consistency
class Events:
    """Event name constants to avoid typos"""
    REGISTRATION_REQUESTED = settings.INNGEST_REGISTER_EVENT
    # Add other events as needed
    WEBSITE_CRAWLED = "website.crawled"
    LINKEDIN_SCRAPED = "linkedin.scraped"
    ANALYSIS_COMPLETED = "analysis.completed"