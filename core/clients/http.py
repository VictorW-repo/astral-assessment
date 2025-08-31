"""
Shared HTTP client factory with proper configuration
Provides a reusable httpx.AsyncClient with timeouts, retries, and headers
"""

import httpx
from typing import Optional, Dict, Any
import logging
from functools import lru_cache

from core.config import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_default_headers() -> Dict[str, str]:
    """
    Get default headers for HTTP requests.
    Cached to avoid recreating on every call.
    """
    return {
        "User-Agent": "Astral-Assessment/1.0 (FastAPI; httpx)",
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache"
    }


class HTTPClientFactory:
    """
    Factory for creating configured httpx.AsyncClient instances.
    Handles timeouts, retries, and default headers.
    """
    
    @staticmethod
    def create(
        timeout: Optional[int] = None,
        max_retries: Optional[int] = None,
        base_url: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        follow_redirects: bool = True
    ) -> httpx.AsyncClient:
        """
        Create a configured httpx.AsyncClient.
        
        Args:
            timeout: Request timeout in seconds (default from settings)
            max_retries: Maximum number of retries (default from settings)
            base_url: Base URL for the client
            headers: Additional headers to include
            follow_redirects: Whether to follow redirects
        
        Returns:
            Configured httpx.AsyncClient
        """
        # Use defaults from settings if not provided
        timeout = timeout or settings.HTTP_TIMEOUT
        max_retries = max_retries or settings.HTTP_MAX_RETRIES
        
        # Merge headers
        default_headers = get_default_headers()
        if headers:
            default_headers.update(headers)
        
        # Configure timeout
        timeout_config = httpx.Timeout(
            timeout=timeout,
            connect=10.0,  # Connection timeout
            read=timeout,   # Read timeout
            write=10.0,     # Write timeout
            pool=5.0        # Pool timeout
        )
        
        # Configure retry transport
        transport = httpx.AsyncHTTPTransport(
            retries=max_retries,
            verify=True,  # Always verify SSL
        )
        
        # Create client
        client = httpx.AsyncClient(
            base_url=base_url,
            headers=default_headers,
            timeout=timeout_config,
            transport=transport,
            follow_redirects=follow_redirects,
            # Limits for connection pooling
            limits=httpx.Limits(
                max_keepalive_connections=10,
                max_connections=100,
                keepalive_expiry=30.0
            )
        )
        
        logger.debug(f"Created HTTP client with timeout={timeout}s, retries={max_retries}")
        
        return client
    
    @staticmethod
    async def request_with_retry(
        client: httpx.AsyncClient,
        method: str,
        url: str,
        max_retries: int = 3,
        **kwargs
    ) -> Optional[httpx.Response]:
        """
        Make an HTTP request with manual retry logic for more control.
        
        Args:
            client: httpx.AsyncClient to use
            method: HTTP method (GET, POST, etc.)
            url: URL to request
            max_retries: Maximum number of retries
            **kwargs: Additional arguments for the request
        
        Returns:
            Response object or None if all retries failed
        """
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                response = await client.request(method, url, **kwargs)
                
                # Check for rate limiting
                if response.status_code == 429:
                    retry_after = response.headers.get('Retry-After', '5')
                    logger.warning(f"Rate limited on {url}, retry after {retry_after}s")
                    # In production, we'd sleep here, but for assessment we'll fail fast
                    if attempt < max_retries:
                        continue
                    return None
                
                # Success or client error (no point retrying)
                if response.status_code < 500:
                    return response
                
                # Server error - retry
                if attempt < max_retries:
                    logger.warning(f"Server error {response.status_code} on {url}, attempt {attempt + 1}/{max_retries + 1}")
                    continue
                    
            except httpx.TimeoutException as e:
                last_exception = e
                if attempt < max_retries:
                    logger.warning(f"Timeout on {url}, attempt {attempt + 1}/{max_retries + 1}")
                    continue
                    
            except httpx.NetworkError as e:
                last_exception = e
                if attempt < max_retries:
                    logger.warning(f"Network error on {url}, attempt {attempt + 1}/{max_retries + 1}: {e}")
                    continue
                    
            except Exception as e:
                last_exception = e
                logger.error(f"Unexpected error on {url}: {e}")
                break
        
        logger.error(f"All retries failed for {url}. Last error: {last_exception}")
        return None


# Singleton instance for shared use
_default_client: Optional[httpx.AsyncClient] = None


async def get_default_client() -> httpx.AsyncClient:
    """
    Get or create the default shared HTTP client.
    Use this for general HTTP requests that don't need special configuration.
    """
    global _default_client
    
    if _default_client is None or _default_client.is_closed:
        _default_client = HTTPClientFactory.create()
    
    return _default_client


async def close_default_client():
    """
    Close the default shared HTTP client.
    Call this on application shutdown.
    """
    global _default_client
    
    if _default_client and not _default_client.is_closed:
        await _default_client.aclose()
        _default_client = None