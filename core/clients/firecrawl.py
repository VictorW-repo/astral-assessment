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
        headers = {}
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
            # Firecrawl crawl endpoint
            endpoint = "/crawl"

            # Request payload - using map method for discovering URLs
            payload = {
                "url": url,
                "mode": "map",  # Map mode returns list of URLs without content
                "limit": min(limit, settings.FIRECRAWL_MAX_URLS),
                "includeSubdomains": False,  # Stay on same domain
                "maxDepth": 3,  # Don't go too deep
                "allowBackwardLinks": False,
                "allowExternalLinks": False,
                "ignoreSitemap": False,  # Use sitemap if available
                "scrapeOptions": {
                    "formats": ["markdown"],  # We'll use markdown later
                    "onlyMainContent": True,
                },
            }

            logger.info(f"Crawling {url} with limit {limit}")

            # Use resilient request method
            response = await self._make_request_with_retry("POST", endpoint, payload)

            # Handle errors (resilient method handles retries)
            if not response.is_success:
                logger.error(f"Firecrawl crawl failed with status {response.status_code}")
                return {"status": "error", "reason": f"http_{response.status_code}", "urls": [url]}

            # Parse response
            data = response.json()

            # Extract URLs from response
            # Firecrawl returns data in different formats depending on mode
            urls = []
            if "data" in data:
                # Map mode returns array of URL objects
                for item in data.get("data", []):
                    if isinstance(item, dict) and "url" in item:
                        urls.append(item["url"])
                    elif isinstance(item, str):
                        urls.append(item)
            elif "urls" in data:
                urls = data["urls"]

            logger.info(f"Discovered {len(urls)} URLs from {url}")

            return {
                "status": "success",
                "urls": urls[:limit],  # Respect limit
                "total_found": len(urls),
            }

        except httpx.HTTPError as e:
            if "Circuit breaker is open" in str(e):
                logger.warning("Firecrawl circuit breaker is open")
                return {"status": "circuit_open", "reason": "circuit_breaker_open", "urls": [url]}
            logger.error(f"HTTP error while crawling {url}: {e}")
            return {"status": "error", "reason": "http_error", "urls": [url]}
        except httpx.TimeoutException:
            logger.error(f"Timeout while crawling {url} (after retries)")
            return {"status": "timeout", "reason": "request_timeout", "urls": [url]}
        except Exception as e:
            logger.error(f"Unexpected error crawling {url}: {e}")
            return {"status": "error", "reason": str(e), "urls": [url]}

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
            # Firecrawl scrape endpoint
            endpoint = "/scrape"

            # Request payload
            payload = {
                "url": url,
                "formats": [format],  # Markdown is best for LLM processing
                "onlyMainContent": True,  # Skip navigation, footers, etc.
                "includeTags": ["h1", "h2", "h3", "p", "li", "strong", "em"],
                "excludeTags": ["script", "style", "nav", "footer", "header"],
                "waitFor": 2000,  # Wait 2s for JS to load
                "timeout": 15000,  # 15s timeout
            }

            logger.info(f"Scraping {url} in {format} format")

            # Use resilient request method
            response = await self._make_request_with_retry("POST", endpoint, payload)

            # Handle errors (resilient method handles retries)
            if not response.is_success:
                logger.error(f"Firecrawl scrape failed with status {response.status_code}")
                return {
                    "status": "error",
                    "reason": f"http_{response.status_code}",
                    "url": url,
                    "content": "",
                }

            # Parse response
            data = response.json()

            # Extract content based on format
            content = ""
            if "data" in data:
                if isinstance(data["data"], dict):
                    # Look for content in various possible fields
                    content = (
                        data["data"].get("markdown", "")
                        or data["data"].get("content", "")
                        or data["data"].get("text", "")
                        or data["data"].get("html", "")
                    )
                elif isinstance(data["data"], str):
                    content = data["data"]
            elif "content" in data:
                content = data["content"]
            elif "markdown" in data:
                content = data["markdown"]

            logger.info(f"Scraped {len(content)} characters from {url}")

            return {"status": "success", "url": url, "content": content, "format": format}

        except httpx.HTTPError as e:
            if "Circuit breaker is open" in str(e):
                logger.warning("Firecrawl circuit breaker is open")
                return {
                    "status": "circuit_open",
                    "reason": "circuit_breaker_open",
                    "url": url,
                    "content": "",
                }
            logger.error(f"HTTP error while scraping {url}: {e}")
            return {"status": "error", "reason": "http_error", "url": url, "content": ""}
        except httpx.TimeoutException:
            logger.error(f"Timeout while scraping {url} (after retries)")
            return {"status": "timeout", "reason": "request_timeout", "url": url, "content": ""}
        except Exception as e:
            logger.error(f"Unexpected error scraping {url}: {e}")
            return {"status": "error", "reason": str(e), "url": url, "content": ""}

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
