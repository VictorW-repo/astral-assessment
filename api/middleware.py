"""
Custom middleware for the FastAPI application
Includes request timing and logging
"""

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Callable
import time
import logging
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)


class RequestTimingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to log request timing and basic request information.
    This is a habit from astral's engineering practices - always measure.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate request ID for tracing
        request_id = str(uuid.uuid4())[:8]  # Short ID for logs
        
        # Start timing
        start_time = time.perf_counter()
        
        # Log incoming request
        logger.info(
            f"[{request_id}] {request.method} {request.url.path} "
            f"from {request.client.host if request.client else 'unknown'}"
        )
        
        # Process request
        try:
            response = await call_next(request)
            
            # Calculate duration
            duration = time.perf_counter() - start_time
            
            # Add timing header
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = f"{duration:.3f}"
            
            # Log completion
            logger.info(
                f"[{request_id}] Completed {request.method} {request.url.path} "
                f"with status {response.status_code} in {duration:.3f}s"
            )
            
            # Warn if request was slow
            if duration > 1.0:
                logger.warning(
                    f"[{request_id}] Slow request: {request.method} {request.url.path} "
                    f"took {duration:.3f}s"
                )
            
            return response
            
        except Exception as e:
            duration = time.perf_counter() - start_time
            logger.error(
                f"[{request_id}] Error processing {request.method} {request.url.path} "
                f"after {duration:.3f}s: {str(e)}",
                exc_info=True
            )
            raise


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Optional: Add security headers to responses
    Not required for the assessment but good practice
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        
        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        return response