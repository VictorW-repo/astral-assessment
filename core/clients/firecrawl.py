"""
Firecrawl API client with graceful fallback for no API key
Handles crawling and scraping with rate limit awareness
"""

import httpx
from typing import Optional, Dict, Any, List
import logging
import asyncio
from urllib.parse import urljoin

from core.config import settings
from core.clients.http import HTTPClientFactory
from core.utils import safe_url, is_valid_url

logger = logging.getLogger(__name__)


class FirecrawlClient:
    """
    Client for interacting with Firecrawl API.
    Gracefully handles missing API key and rate limits.
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
        
        # Create HTTP client with Firecrawl-specific config
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        self.client = HTTPClientFactory.create(
            base_url=self.base_url,
            headers=headers,
            timeout=settings.FIRECRAWL_TIMEOUT
        )
        
        logger.info(f"Firecrawl client initialized (API key: {'present' if self.has_key else 'absent'})")
    
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
                "urls": [url]  # Return at least the provided URL
            }
        
        # Normalize URL
        url = safe_url(url)
        if not url:
            return {
                "status": "error",
                "reason": "invalid_url",
                "urls": []
            }
        
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
                    "onlyMainContent": True
                }
            }
            
            logger.info(f"Crawling {url} with limit {limit}")
            
            response = await self.client.post(endpoint, json=payload)
            
            # Handle rate limiting
            if response.status_code == 429:
                logger.warning(f"Rate limited while crawling {url}")
                return {
                    "status": "rate_limited",
                    "reason": "firecrawl_rate_limit",
                    "urls": [url]
                }
            
            # Handle errors
            if response.status_code != 200:
                logger.error(f"Firecrawl crawl failed with status {response.status_code}: {response.text}")
                return {
                    "status": "error",
                    "reason": f"http_{response.status_code}",
                    "urls": [url]
                }
            
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
                "total_found": len(urls)
            }
            
        except httpx.TimeoutException:
            logger.error(f"Timeout while crawling {url}")
            return {
                "status": "timeout",
                "reason": "request_timeout",
                "urls": [url]
            }
        except Exception as e:
            logger.error(f"Error crawling {url}: {e}")
            return {
                "status": "error",
                "reason": str(e),
                "urls": [url]
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
                "content": f"[Content from {url} would be scraped here]"
            }
        
        # Normalize URL
        url = safe_url(url)
        if not url:
            return {
                "status": "error",
                "reason": "invalid_url",
                "url": url,
                "content": ""
            }
        
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
                "timeout": 15000  # 15s timeout
            }
            
            logger.info(f"Scraping {url} in {format} format")
            
            response = await self.client.post(endpoint, json=payload)
            
            # Handle rate limiting
            if response.status_code == 429:
                logger.warning(f"Rate limited while scraping {url}")
                return {
                    "status": "rate_limited",
                    "reason": "firecrawl_rate_limit",
                    "url": url,
                    "content": ""
                }
            
            # Handle errors
            if response.status_code != 200:
                logger.error(f"Firecrawl scrape failed with status {response.status_code}")
                return {
                    "status": "error",
                    "reason": f"http_{response.status_code}",
                    "url": url,
                    "content": ""
                }
            
            # Parse response
            data = response.json()
            
            # Extract content based on format
            content = ""
            if "data" in data:
                if isinstance(data["data"], dict):
                    # Look for content in various possible fields
                    content = (
                        data["data"].get("markdown", "") or
                        data["data"].get("content", "") or
                        data["data"].get("text", "") or
                        data["data"].get("html", "")
                    )
                elif isinstance(data["data"], str):
                    content = data["data"]
            elif "content" in data:
                content = data["content"]
            elif "markdown" in data:
                content = data["markdown"]
            
            logger.info(f"Scraped {len(content)} characters from {url}")
            
            return {
                "status": "success",
                "url": url,
                "content": content,
                "format": format
            }
            
        except httpx.TimeoutException:
            logger.error(f"Timeout while scraping {url}")
            return {
                "status": "timeout",
                "reason": "request_timeout",
                "url": url,
                "content": ""
            }
        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            return {
                "status": "error",
                "reason": str(e),
                "url": url,
                "content": ""
            }
    
    async def batch_scrape(self, urls: List[str], format: str = "markdown", max_concurrent: int = 3) -> List[Dict[str, Any]]:
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