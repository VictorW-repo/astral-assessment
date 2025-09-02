"""
Firecrawl API client with graceful fallback for no API key
Handles crawling and scraping with rate limit awareness
"""

import httpx
from typing import Optional, Dict, Any, List
import logging
import asyncio
import random
import time
from urllib.parse import urljoin
from collections import deque
from datetime import datetime, timedelta

from core.config import settings
from core.clients.http import HTTPClientFactory
from core.utils import safe_url, is_valid_url

logger = logging.getLogger(__name__)


class FirecrawlClient:
    """
    Client for interacting with Firecrawl API.
    Gracefully handles missing API key and rate limits with exponential backoff.
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Firecrawl client.

        Args:
            api_key: Firecrawl API key (optional)
        """
        self.api_key = api_key or settings.FIRECRAWL_API_KEY
        self.base_url = settings.FIRECRAWL_API_URL
        self.has_key = bool(self.api_key)

        # Rate limiting tracking
        self.request_times = deque()
        self.rate_limit_per_minute = settings.FIRECRAWL_REQUESTS_PER_MINUTE

        # Circuit breaker state
        self.failure_count = 0
        self.last_failure_time = None
        self.circuit_open = False

        # Create HTTP client with Firecrawl-specific config
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        self.client = HTTPClientFactory.create(
            base_url=self.base_url, headers=headers, timeout=settings.FIRECRAWL_TIMEOUT
        )

        logger.info(
            f"Firecrawl client initialized (API key: {'present' if self.has_key else 'absent'})"
        )

    async def _wait_for_rate_limit(self):
        """Enforce rate limiting by waiting if necessary."""
        if not self.has_key:
            return  # No rate limiting for mock responses

        now = datetime.now()

        # Remove old requests (older than 1 minute)
        while self.request_times and self.request_times[0] < now - timedelta(minutes=1):
            self.request_times.popleft()

        # Check if we're at the rate limit
        if len(self.request_times) >= self.rate_limit_per_minute:
            sleep_time = 60 - (now - self.request_times[0]).total_seconds()
            if sleep_time > 0:
                logger.info(f"Rate limit reached, waiting {sleep_time:.2f} seconds")
                await asyncio.sleep(sleep_time)

        # Record this request
        self.request_times.append(now)

    def _calculate_backoff_delay(self, attempt: int) -> float:
        """Calculate exponential backoff delay with jitter."""
        base_delay = settings.FIRECRAWL_BASE_DELAY_SECONDS
        max_delay = settings.FIRECRAWL_MAX_DELAY_SECONDS

        # Exponential backoff: base_delay * (2 ** attempt)
        delay = min(base_delay * (2**attempt), max_delay)

        # Add jitter (random variation ±25%)
        jitter = delay * 0.25 * (random.random() * 2 - 1)
        delay += jitter

        return max(0, delay)

    def _is_retryable_error(self, status_code: int, error: Exception = None) -> bool:
        """Determine if an error is retryable."""
        # Rate limits are always retryable
        if status_code == 429:
            return True

        # Server errors are retryable
        if 500 <= status_code < 600:
            return True

        # Timeout errors are retryable
        if isinstance(error, (httpx.TimeoutException, asyncio.TimeoutError)):
            return True

        # Connection errors are retryable
        if isinstance(error, (httpx.ConnectError, httpx.NetworkError)):
            return True

        # Client errors (4xx except 429) are not retryable
        return False

    def _record_success(self):
        """Record a successful API call."""
        self.failure_count = 0
        self.circuit_open = False

    def _record_failure(self):
        """Record a failed API call."""
        self.failure_count += 1
        self.last_failure_time = datetime.now()

        # Open circuit breaker if too many failures
        if self.failure_count >= 5:
            self.circuit_open = True
            logger.warning("Firecrawl circuit breaker opened due to repeated failures")

    def _is_circuit_open(self) -> bool:
        """Check if circuit breaker is open."""
        if not self.circuit_open:
            return False

        # Try to recover after 60 seconds
        if self.last_failure_time and datetime.now() - self.last_failure_time > timedelta(
            seconds=60
        ):
            logger.info("Attempting to close Firecrawl circuit breaker")
            self.circuit_open = False
            self.failure_count = 0
            return False

        return True

    async def _make_request_with_retry(
        self, method: str, endpoint: str, json_data: Dict[str, Any] = None
    ) -> httpx.Response:
        """Make HTTP request with exponential backoff retry logic."""
        if self._is_circuit_open():
            logger.warning("Circuit breaker is open, skipping Firecrawl request")
            raise httpx.HTTPError("Circuit breaker is open")

        # Build full URL for logging
        full_url = f"{self.base_url}{endpoint}"
        
        # Log request details (but redact API key)
        headers_log = dict(self.client.headers) if hasattr(self.client, 'headers') else {}
        if 'Authorization' in headers_log:
            headers_log['Authorization'] = 'Bearer [REDACTED]'
        
        logger.info(f"Firecrawl API Request - {method.upper()} {full_url}")
        logger.info(f"Request Headers: {headers_log}")
        if json_data:
            logger.info(f"Request Payload: {json_data}")

        last_exception = None

        for attempt in range(settings.FIRECRAWL_MAX_RETRIES + 1):
            try:
                # Wait for rate limit before making request
                await self._wait_for_rate_limit()

                # Make the request
                if method.upper() == "POST":
                    response = await self.client.post(endpoint, json=json_data)
                else:
                    response = await self.client.get(endpoint)

                # Log response details
                logger.info(f"Firecrawl API Response - Status: {response.status_code}")
                try:
                    response_text = response.text
                    if response_text:
                        logger.info(f"Response Body: {response_text}")
                    else:
                        logger.info("Response Body: (empty)")
                except Exception as e:
                    logger.warning(f"Could not log response body: {e}")

                # Check for rate limiting
                if response.status_code == 429:
                    if attempt < settings.FIRECRAWL_MAX_RETRIES:
                        delay = self._calculate_backoff_delay(attempt)
                        logger.warning(
                            f"Rate limited, backing off for {delay:.2f} seconds (attempt {attempt + 1})"
                        )
                        await asyncio.sleep(delay)
                        continue

                # Check for other retryable errors
                if not response.is_success and self._is_retryable_error(response.status_code):
                    if attempt < settings.FIRECRAWL_MAX_RETRIES:
                        delay = self._calculate_backoff_delay(attempt)
                        logger.warning(
                            f"HTTP {response.status_code} error, retrying in {delay:.2f} seconds (attempt {attempt + 1})"
                        )
                        await asyncio.sleep(delay)
                        continue

                # Success or non-retryable error
                if response.is_success:
                    self._record_success()
                else:
                    self._record_failure()

                return response

            except Exception as e:
                last_exception = e

                if self._is_retryable_error(0, e) and attempt < settings.FIRECRAWL_MAX_RETRIES:
                    delay = self._calculate_backoff_delay(attempt)
                    logger.warning(
                        f"Request failed with {type(e).__name__}, retrying in {delay:.2f} seconds (attempt {attempt + 1})"
                    )
                    await asyncio.sleep(delay)
                    continue

                # Non-retryable error or max retries reached
                self._record_failure()
                raise e

        # If we get here, max retries exceeded
        self._record_failure()
        if last_exception:
            raise last_exception
        else:
            raise httpx.HTTPError("Max retries exceeded")

    async def crawl(self, url: str, limit: int = 50) -> Dict[str, Any]:
        """
        Crawl a website to discover URLs.

        Args:
            url: Starting URL to crawl
            limit: Maximum number of URLs to return

        Returns:
            Dict with status and discovered URLs or error info
        """
        if not self.has_key:
            logger.warning("No Firecrawl API key - returning mock crawl response")
            return {
                "status": "skipped",
                "reason": "no_api_key",
                "urls": [url],  # Return at least the provided URL
            }

        # Normalize URL
        url = safe_url(url)
        if not url:
            return {"status": "error", "reason": "invalid_url", "urls": []}

        try:
            # Firecrawl v2 crawl endpoint - async job-based
            endpoint = "/crawl"

            # v2 API request payload - much simpler than v1
            payload = {
                "url": url,
                "limit": min(limit, settings.FIRECRAWL_MAX_URLS)
            }

            logger.info(f"Starting crawl job for {url} with limit {limit} (v2 API)")

            # Step 1: Start the crawl job
            response = await self._make_request_with_retry("POST", endpoint, payload)

            # Handle errors (resilient method handles retries)
            if not response.is_success:
                logger.error(f"Firecrawl crawl failed with status {response.status_code}")
                error_code = f"http_{response.status_code}"
                from core.utils import get_human_readable_error
                return {
                    "status": "error", 
                    "reason": error_code, 
                    "urls": [url],
                    "human_readable_error": get_human_readable_error(error_code)
                }

            # Parse v2 API job response
            data = response.json()

            # v2 API response structure: {"success": true, "id": "job-id"}
            if not data.get("success"):
                logger.error(f"Firecrawl API returned success=false: {data}")
                return {
                    "status": "error",
                    "reason": "api_failure",
                    "urls": [url],
                    "human_readable_error": "API request failed"
                }

            # Extract job ID from response
            job_id = data.get("id")
            if not job_id:
                logger.error(f"No job ID returned from crawl API: {data}")
                return {
                    "status": "error",
                    "reason": "no_job_id",
                    "urls": [url],
                    "human_readable_error": "Crawl job could not be started"
                }

            logger.info(f"Started crawl job {job_id}, polling for completion...")

            # Step 2: Poll for job completion
            return await self._poll_crawl_job(job_id, url, limit)

        except httpx.HTTPError as e:
            if "Circuit breaker is open" in str(e):
                logger.warning("Firecrawl circuit breaker is open")
                from core.utils import get_human_readable_error
                return {
                    "status": "circuit_open", 
                    "reason": "circuit_breaker_open", 
                    "urls": [url],
                    "human_readable_error": get_human_readable_error("circuit_breaker_open")
                }
            logger.error(f"HTTP error while crawling {url}: {e}")
            from core.utils import get_human_readable_error
            return {
                "status": "error", 
                "reason": "http_error", 
                "urls": [url],
                "human_readable_error": get_human_readable_error("http_error")
            }
        except httpx.TimeoutException:
            logger.error(f"Timeout while crawling {url} (after retries)")
            from core.utils import get_human_readable_error
            return {
                "status": "timeout", 
                "reason": "request_timeout", 
                "urls": [url],
                "human_readable_error": get_human_readable_error("request_timeout")
            }
        except Exception as e:
            logger.error(f"Unexpected error crawling {url}: {e}")
            error_reason = str(e)
            from core.utils import get_human_readable_error
            return {
                "status": "error", 
                "reason": error_reason, 
                "urls": [url],
                "human_readable_error": get_human_readable_error(error_reason) or f"Unexpected error: {error_reason}"
            }

    async def _poll_crawl_job(self, job_id: str, original_url: str, limit: int) -> Dict[str, Any]:
        """
        Poll a crawl job until completion and return the results.
        
        Args:
            job_id: The job ID returned from the crawl start request
            original_url: The original URL for fallback purposes
            limit: The URL limit for the crawl
            
        Returns:
            Dict with crawl results or error info
        """
        import time
        
        start_time = time.time()
        max_wait = settings.FIRECRAWL_CRAWL_MAX_WAIT
        poll_interval = settings.FIRECRAWL_CRAWL_POLL_INTERVAL
        
        while time.time() - start_time < max_wait:
            try:
                # Check job status
                endpoint = f"/crawl/{job_id}"
                response = await self._make_request_with_retry("GET", endpoint)
                
                if not response.is_success:
                    logger.error(f"Failed to check crawl status: HTTP {response.status_code}")
                    # Don't immediately fail - try a few more times
                    await asyncio.sleep(poll_interval)
                    continue
                
                data = response.json()
                
                if not data.get("success"):
                    logger.error(f"Crawl status API returned success=false: {data}")
                    await asyncio.sleep(poll_interval) 
                    continue
                
                status = data.get("status", "unknown")
                logger.debug(f"Crawl job {job_id} status: {status}")
                
                if status == "completed":
                    # Extract URLs and content from completed crawl
                    return self._parse_completed_crawl(data, limit)
                    
                elif status == "failed":
                    logger.error(f"Crawl job {job_id} failed: {data}")
                    from core.utils import get_human_readable_error
                    return {
                        "status": "error",
                        "reason": "crawl_failed",
                        "urls": [original_url],
                        "human_readable_error": get_human_readable_error("crawl_failed") or "Crawl job failed"
                    }
                    
                elif status in ["scraping", "processing", "queued"]:
                    # Job is still running
                    completed = data.get("completed", 0)
                    total = data.get("total", "?")
                    logger.debug(f"Crawl job {job_id} in progress: {completed}/{total}")
                    
                    # Wait before next poll
                    await asyncio.sleep(poll_interval)
                    continue
                    
                else:
                    logger.warning(f"Unknown crawl status: {status}")
                    await asyncio.sleep(poll_interval)
                    continue
                    
            except Exception as e:
                logger.error(f"Error polling crawl job {job_id}: {e}")
                await asyncio.sleep(poll_interval)
                continue
        
        # Timeout reached
        logger.warning(f"Crawl job {job_id} timed out after {max_wait} seconds")
        from core.utils import get_human_readable_error
        return {
            "status": "timeout",
            "reason": "crawl_timeout", 
            "urls": [original_url],
            "human_readable_error": get_human_readable_error("request_timeout") or "Crawl job timed out"
        }

    def _parse_completed_crawl(self, data: Dict[str, Any], limit: int) -> Dict[str, Any]:
        """
        Parse completed crawl job data and extract URLs and content.
        
        Args:
            data: The completed crawl job response
            limit: URL limit to respect
            
        Returns:
            Dict with discovered URLs and content
        """
        urls = []
        scraped_content = []
        
        # Extract data items from the crawl response
        data_items = data.get("data", [])
        
        if isinstance(data_items, list):
            for item in data_items:
                if isinstance(item, dict):
                    # Extract URL from metadata
                    source_url = None
                    if "metadata" in item and isinstance(item["metadata"], dict):
                        source_url = item["metadata"].get("sourceURL")
                    
                    if not source_url and "url" in item:
                        source_url = item["url"]
                    
                    if source_url:
                        urls.append(source_url)
                        
                        # Extract content if available (v2 crawl includes content)
                        content = item.get("markdown", "") or item.get("html", "") or ""
                        scraped_content.append({
                            "url": source_url,
                            "content": content,
                            "status": "success" if content else "no_content"
                        })
        
        logger.info(f"Parsed crawl results: {len(urls)} URLs discovered, {len(scraped_content)} with content")
        
        return {
            "status": "success",
            "urls": urls[:limit],  # Respect limit
            "total_found": len(urls),
            "scraped_content": scraped_content[:limit]  # Also include content from crawl
        }

    async def scrape(self, url: str, format: str = "markdown") -> Dict[str, Any]:
        """
        Scrape content from a single URL.

        Args:
            url: URL to scrape
            format: Output format (markdown, html, text)

        Returns:
            Dict with status and content or error info
        """
        if not self.has_key:
            logger.warning("No Firecrawl API key - returning mock scrape response")
            return {
                "status": "skipped",
                "reason": "no_api_key",
                "url": url,
                "content": f"[Content from {url} would be scraped here]",
            }

        # Normalize URL
        url = safe_url(url)
        if not url:
            return {"status": "error", "reason": "invalid_url", "url": url, "content": ""}

        try:
            # Firecrawl v2 scrape endpoint
            endpoint = "/scrape"

            # v2 API request payload - simplified structure
            payload = {
                "url": url,
                "formats": [format]  # v2 API expects array of formats
            }

            logger.info(f"Scraping {url} in {format} format (v2 API)")

            # Use resilient request method
            response = await self._make_request_with_retry("POST", endpoint, payload)

            # Handle errors (resilient method handles retries)
            if not response.is_success:
                logger.error(f"Firecrawl scrape failed with status {response.status_code}")
                error_code = f"http_{response.status_code}"
                from core.utils import get_human_readable_error
                return {
                    "status": "error",
                    "reason": error_code,
                    "url": url,
                    "content": "",
                    "human_readable_error": get_human_readable_error(error_code)
                }

            # Parse v2 API response
            data = response.json()

            # v2 API response structure: {"success": true, "data": {...}}
            if not data.get("success"):
                logger.error(f"Firecrawl API returned success=false: {data}")
                return {
                    "status": "error",
                    "reason": "api_failure",
                    "url": url,
                    "content": "",
                    "human_readable_error": "API request failed"
                }

            # Extract content from v2 response data
            content = ""
            data_obj = data.get("data", {})
            
            if isinstance(data_obj, dict):
                # v2 API returns content directly under format name
                if format == "markdown":
                    content = data_obj.get("markdown", "")
                elif format == "html":
                    content = data_obj.get("html", "")
                elif format == "text":
                    content = data_obj.get("text", "")
                else:
                    # Fallback: try to find any content
                    content = (
                        data_obj.get("markdown", "") 
                        or data_obj.get("html", "") 
                        or data_obj.get("text", "")
                    )

            logger.info(f"Scraped {len(content)} characters from {url}")

            return {"status": "success", "url": url, "content": content, "format": format}

        except httpx.HTTPError as e:
            if "Circuit breaker is open" in str(e):
                logger.warning("Firecrawl circuit breaker is open")
                from core.utils import get_human_readable_error
                return {
                    "status": "circuit_open",
                    "reason": "circuit_breaker_open",
                    "url": url,
                    "content": "",
                    "human_readable_error": get_human_readable_error("circuit_breaker_open")
                }
            logger.error(f"HTTP error while scraping {url}: {e}")
            from core.utils import get_human_readable_error
            return {
                "status": "error", 
                "reason": "http_error", 
                "url": url, 
                "content": "",
                "human_readable_error": get_human_readable_error("http_error")
            }
        except httpx.TimeoutException:
            logger.error(f"Timeout while scraping {url} (after retries)")
            from core.utils import get_human_readable_error
            return {
                "status": "timeout", 
                "reason": "request_timeout", 
                "url": url, 
                "content": "",
                "human_readable_error": get_human_readable_error("request_timeout")
            }
        except Exception as e:
            logger.error(f"Unexpected error scraping {url}: {e}")
            error_reason = str(e)
            from core.utils import get_human_readable_error
            return {
                "status": "error", 
                "reason": error_reason, 
                "url": url, 
                "content": "",
                "human_readable_error": get_human_readable_error(error_reason) or f"Unexpected error: {error_reason}"
            }

    async def batch_scrape(
        self, urls: List[str], format: str = "markdown", max_concurrent: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Scrape multiple URLs concurrently with rate limit awareness.

        Args:
            urls: List of URLs to scrape
            format: Output format
            max_concurrent: Maximum concurrent requests

        Returns:
            List of scrape results
        """
        if not urls:
            return []

        # Limit concurrency to avoid rate limits
        semaphore = asyncio.Semaphore(max_concurrent)

        async def scrape_with_semaphore(url: str) -> Dict[str, Any]:
            async with semaphore:
                # Add small delay between requests to be nice
                await asyncio.sleep(0.5)
                return await self.scrape(url, format)

        # Scrape all URLs concurrently
        tasks = [scrape_with_semaphore(url) for url in urls]
        results = await asyncio.gather(*tasks)

        return results

    async def validate_api_key(self) -> Dict[str, Any]:
        """
        Validate API key by making a simple request to check authentication.
        Returns status and details about the API key validity.
        """
        if not self.api_key:
            return {
                "status": "no_key",
                "valid": False,
                "message": "No API key configured"
            }

        try:
            logger.info("Validating Firecrawl API key...")
            
            # Try to scrape a simple URL that should work with any valid key
            # Using a minimal request to minimize credit usage
            test_url = "https://example.com"
            endpoint = "/scrape"
            
            payload = {
                "url": test_url,
                "formats": ["markdown"]
            }

            response = await self._make_request_with_retry("POST", endpoint, payload)
            
            if response.status_code == 401:
                return {
                    "status": "invalid_key",
                    "valid": False,
                    "message": "API key is invalid or expired"
                }
            elif response.status_code == 402:
                return {
                    "status": "no_credits",
                    "valid": True,  # Key is valid, just no credits
                    "message": "API key is valid but account has insufficient credits"
                }
            elif response.status_code == 403:
                return {
                    "status": "forbidden",
                    "valid": False,
                    "message": "API key lacks required permissions"
                }
            elif response.is_success:
                return {
                    "status": "valid",
                    "valid": True,
                    "message": "API key is valid and working"
                }
            else:
                return {
                    "status": "error",
                    "valid": False,
                    "message": f"Unexpected response status: {response.status_code}"
                }

        except Exception as e:
            logger.error(f"Error validating API key: {e}")
            return {
                "status": "error",
                "valid": False,
                "message": f"Validation failed: {str(e)}"
            }

    async def close(self):
        """Close the HTTP client."""
        if not self.client.is_closed:
            await self.client.aclose()


# Module-level functions for convenience
_client: Optional[FirecrawlClient] = None


async def get_firecrawl_client() -> FirecrawlClient:
    """Get or create the default Firecrawl client."""
    global _client
    if _client is None:
        _client = FirecrawlClient()
    return _client


async def crawl(url: str, limit: int = 50) -> Dict[str, Any]:
    """Convenience function to crawl a URL."""
    client = await get_firecrawl_client()
    return await client.crawl(url, limit)


async def scrape(url: str, format: str = "markdown") -> Dict[str, Any]:
    """Convenience function to scrape a URL."""
    client = await get_firecrawl_client()
    return await client.scrape(url, format)


async def batch_scrape(urls: List[str], format: str = "markdown") -> List[Dict[str, Any]]:
    """Convenience function to batch scrape URLs."""
    client = await get_firecrawl_client()
    return await client.batch_scrape(urls, format)


async def validate_api_key() -> Dict[str, Any]:
    """Convenience function to validate the API key."""
    client = await get_firecrawl_client()
    return await client.validate_api_key()
