"""
URL scraping module - Phase 3 of website analysis.
Extracts content from filtered URLs using Firecrawl.
"""

import logging
from typing import List, Dict, Any, Optional
import asyncio
import httpx
from urllib.parse import urlparse
import re

from core.clients import firecrawl
from core.config import settings
from core.utils import truncate_text, clean_text

logger = logging.getLogger(__name__)


async def scrape_urls(
    urls: List[str],
    format: str = "markdown"
) -> Dict[str, Any]:
    """
    Scrape content from filtered URLs.
    Uses Firecrawl's scraping capabilities with markdown format for LLM processing.
    
    Phase 3: Content Extraction
    - Uses markdown format (best for LLM processing)
    - Handles rate limits gracefully
    - Processes URLs in batches to avoid overwhelming the API
    
    Args:
        urls: List of URLs to scrape
        format: Output format (markdown recommended for LLMs)
    
    Returns:
        Dict with scraped content and statistics
    """
    if not urls:
        return {
            "results": [],
            "stats": {
                "total": 0,
                "success": 0,
                "failed": 0
            }
        }
    
    logger.info(f"Starting content scraping for {len(urls)} URLs in {format} format")
    
    # First try Firecrawl batch scraping
    try:
        scrape_results = await firecrawl.batch_scrape(urls, format=format)
    except Exception as e:
        logger.error(f"Firecrawl batch scraping failed: {e}")
        scrape_results = [{"status": "error", "reason": "api_error"} for _ in urls]
    
    # Check if all results failed with 402 errors - if so, try fallback
    all_failed_payment = all(
        result.get("status") == "error" and result.get("reason") == "http_402" 
        for result in scrape_results
    )
    
    if all_failed_payment and any(is_simple_scrape_url(url) for url in urls):
        logger.info("All Firecrawl scraping failed with 402 errors - trying fallback scraping for simple URLs")
        fallback_results = []
        
        for i, url in enumerate(urls):
            if is_simple_scrape_url(url):
                logger.info(f"Attempting fallback scraping for {url}")
                fallback_result = await fallback_scrape(url, format)
                fallback_results.append(fallback_result)
            else:
                # Keep the original failed result
                fallback_results.append(scrape_results[i])
        
        scrape_results = fallback_results
    
    # Process results
    processed_results = []
    success_count = 0
    failed_count = 0
    
    for i, result in enumerate(scrape_results):
        url = urls[i] if i < len(urls) else "unknown"
        
        processed = {
            "url": result.get("url", url),
            "status": result.get("status", "unknown")
        }
        
        if result.get("status") == "success":
            # Clean and process content
            content = result.get("content", "")
            
            # Clean the content
            if content:
                content = clean_text(content)
                
                # For markdown, do some additional cleanup
                if format == "markdown":
                    content = clean_markdown(content)
            
            processed["content"] = content
            processed["content_length"] = len(content)
            processed["format"] = result.get("format", format)
            
            success_count += 1
            logger.debug(f"Successfully scraped {url}: {len(content)} chars")
            
        else:
            # Failed to scrape
            processed["content"] = ""
            processed["reason"] = result.get("reason", "unknown_error")
            
            # Add human-readable error message if available
            human_readable_error = result.get("human_readable_error")
            if human_readable_error:
                processed["human_readable_error"] = human_readable_error
            else:
                # Generate human-readable error if not provided by client
                from core.utils import get_human_readable_error
                processed["human_readable_error"] = get_human_readable_error(processed["reason"])
            
            failed_count += 1
            logger.warning(f"Failed to scrape {url}: {result.get('reason', 'unknown')}")
        
        processed_results.append(processed)
    
    # Log summary
    logger.info(f"Scraping complete: {success_count} success, {failed_count} failed")
    
    return {
        "results": processed_results,
        "stats": {
            "total": len(urls),
            "success": success_count,
            "failed": failed_count,
            "success_rate": round(success_count / len(urls) * 100, 1) if urls else 0
        }
    }


def clean_markdown(content: str) -> str:
    """
    Clean markdown content for better LLM processing.
    
    Args:
        content: Raw markdown content
    
    Returns:
        Cleaned markdown
    """
    import re
    
    # Remove excessive newlines
    content = re.sub(r'\n{3,}', '\n\n', content)
    
    # Remove excessive spaces
    content = re.sub(r' {2,}', ' ', content)
    
    # Clean up markdown links that might be broken
    # [text]() -> text
    content = re.sub(r'\[([^\]]+)\]\(\)', r'\1', content)
    
    # Remove empty headers
    content = re.sub(r'^#{1,6}\s*$', '', content, flags=re.MULTILINE)
    
    # Remove excessive horizontal rules
    content = re.sub(r'(---+\n){2,}', '---\n', content)
    
    # Clean up bullet points
    content = re.sub(r'^[\*\-]\s*$', '', content, flags=re.MULTILINE)
    
    # Trim each line
    lines = content.split('\n')
    lines = [line.rstrip() for line in lines]
    content = '\n'.join(lines)
    
    return content.strip()


async def extract_key_information(content: str, url: str) -> Dict[str, Any]:
    """
    Extract key business information from scraped content.
    This could be enhanced with LLM processing in the future.
    
    Args:
        content: Scraped content
        url: Source URL for context
    
    Returns:
        Dict with extracted information
    """
    import re
    
    extracted = {
        "url": url,
        "emails": [],
        "phone_numbers": [],
        "social_links": [],
        "key_sections": []
    }
    
    if not content:
        return extracted
    
    # Extract emails
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    extracted["emails"] = list(set(re.findall(email_pattern, content)))
    
    # Extract phone numbers (basic US format)
    phone_pattern = r'\b(?:\+?1[-.]?)?\(?[0-9]{3}\)?[-.]?[0-9]{3}[-.]?[0-9]{4}\b'
    extracted["phone_numbers"] = list(set(re.findall(phone_pattern, content)))
    
    # Extract social media links
    social_patterns = [
        (r'(?:https?://)?(?:www\.)?linkedin\.com/[^\s<>"{}|\\^`\[\]]+', 'linkedin'),
        (r'(?:https?://)?(?:www\.)?twitter\.com/[^\s<>"{}|\\^`\[\]]+', 'twitter'),
        (r'(?:https?://)?(?:www\.)?facebook\.com/[^\s<>"{}|\\^`\[\]]+', 'facebook'),
        (r'(?:https?://)?(?:www\.)?instagram\.com/[^\s<>"{}|\\^`\[\]]+', 'instagram'),
        (r'(?:https?://)?(?:www\.)?github\.com/[^\s<>"{}|\\^`\[\]]+', 'github'),
    ]
    
    for pattern, platform in social_patterns:
        matches = re.findall(pattern, content, re.IGNORECASE)
        for match in matches:
            extracted["social_links"].append({
                "platform": platform,
                "url": match
            })
    
    # Extract key sections (headers in markdown)
    if '#' in content:  # Markdown headers
        headers = re.findall(r'^#{1,3}\s+(.+)$', content, re.MULTILINE)
        extracted["key_sections"] = headers[:10]  # First 10 headers
    
    # Look for company description patterns
    description_patterns = [
        r'(?:We are|Our company is|We\'re)\s+([^.]+\.)',
        r'(?:Our mission is|Mission:)\s+([^.]+\.)',
        r'(?:Founded in|Established in)\s+(\d{4}[^.]*\.)',
    ]
    
    descriptions = []
    for pattern in description_patterns:
        matches = re.findall(pattern, content, re.IGNORECASE)
        descriptions.extend(matches)
    
    if descriptions:
        extracted["company_descriptions"] = descriptions[:3]  # First 3 matches
    
    return extracted


def get_content_summary(content: str, max_length: int = 500) -> str:
    """
    Generate a summary of the content for quick review.
    
    Args:
        content: Full content
        max_length: Maximum summary length
    
    Returns:
        Summary string
    """
    if not content:
        return "No content available"
    
    # For markdown, try to get first paragraph after first header
    if '#' in content:
        # Split by headers
        sections = content.split('#')
        for section in sections[1:]:  # Skip first (before any header)
            # Get first substantial paragraph
            lines = section.split('\n')
            for line in lines:
                line = line.strip()
                if len(line) > 50:  # Substantial line
                    return truncate_text(line, max_length)
    
    # Fallback: just truncate from beginning
    # Skip any initial whitespace or special characters
    content = content.lstrip('#*- \n')
    return truncate_text(content, max_length)


async def validate_scraped_content(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Validate and assess quality of scraped content.
    
    Args:
        results: List of scraping results
    
    Returns:
        Validation report
    """
    validation = {
        "total_urls": len(results),
        "successful_scrapes": 0,
        "empty_content": 0,
        "low_quality": 0,
        "high_quality": 0,
        "average_content_length": 0,
        "issues": []
    }
    
    total_length = 0
    
    for result in results:
        if result.get("status") == "success":
            validation["successful_scrapes"] += 1
            
            content = result.get("content", "")
            content_length = len(content)
            total_length += content_length
            
            if content_length == 0:
                validation["empty_content"] += 1
                validation["issues"].append(f"Empty content: {result['url']}")
            elif content_length < 100:
                validation["low_quality"] += 1
                validation["issues"].append(f"Very short content ({content_length} chars): {result['url']}")
            elif content_length > 1000:
                validation["high_quality"] += 1
    
    if validation["successful_scrapes"] > 0:
        validation["average_content_length"] = round(total_length / validation["successful_scrapes"])
    
    # Success rate
    validation["success_rate"] = round(
        validation["successful_scrapes"] / validation["total_urls"] * 100, 1
    ) if validation["total_urls"] > 0 else 0
    
    return validation


def is_simple_scrape_url(url: str) -> bool:
    """
    Check if a URL is suitable for simple fallback scraping.
    Returns True for basic websites like example.com that can be scraped without heavy processing.
    
    Args:
        url: URL to check
        
    Returns:
        bool: True if suitable for fallback scraping
    """
    parsed = urlparse(url)
    
    # Allow example.com and other simple test domains
    simple_domains = {"example.com", "example.org", "example.net", "httpbin.org"}
    if parsed.netloc.lower() in simple_domains:
        return True
    
    # Allow any URL that looks like a simple homepage or basic page
    path = parsed.path.lower().strip("/")
    if not path or path in {"index.html", "about", "contact", "home"}:
        return True
    
    return False


async def fallback_scrape(url: str, format: str = "markdown") -> Dict[str, Any]:
    """
    Simple fallback scraping for when Firecrawl API is unavailable.
    Uses basic HTTP client to fetch and convert content.
    
    Args:
        url: URL to scrape
        format: Desired output format (markdown or text)
        
    Returns:
        Dict with scraping result
    """
    try:
        logger.info(f"Attempting fallback scraping for {url}")
        
        # Simple HTTP fetch
        timeout = httpx.Timeout(30.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()
            
        html_content = response.text
        
        # Convert HTML to markdown/text (basic conversion)
        if format == "markdown":
            content = html_to_markdown(html_content)
        else:
            content = html_to_text(html_content)
        
        # Clean the content
        content = clean_text(content)
        
        logger.info(f"Fallback scraping successful for {url}: {len(content)} characters")
        
        return {
            "status": "success",
            "url": url,
            "content": content,
            "format": format,
            "method": "fallback_scraping"
        }
        
    except httpx.HTTPStatusError as e:
        logger.warning(f"HTTP error during fallback scraping of {url}: {e.response.status_code}")
        return {
            "status": "error",
            "url": url,
            "content": "",
            "reason": f"http_{e.response.status_code}",
            "human_readable_error": f"HTTP {e.response.status_code} error when fetching the page"
        }
        
    except httpx.TimeoutException:
        logger.warning(f"Timeout during fallback scraping of {url}")
        return {
            "status": "error", 
            "url": url,
            "content": "",
            "reason": "timeout",
            "human_readable_error": "Page took too long to load"
        }
        
    except Exception as e:
        logger.error(f"Error during fallback scraping of {url}: {e}")
        return {
            "status": "error",
            "url": url, 
            "content": "",
            "reason": "scraping_error",
            "human_readable_error": f"Failed to scrape page: {str(e)}"
        }


def html_to_markdown(html: str) -> str:
    """
    Convert HTML to basic markdown format.
    Very simple conversion - just extracts text and preserves basic structure.
    
    Args:
        html: HTML content
        
    Returns:
        Basic markdown content
    """
    # Remove script and style elements
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
    
    # Convert headers
    html = re.sub(r'<h1[^>]*>(.*?)</h1>', r'# \1\n', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<h2[^>]*>(.*?)</h2>', r'## \1\n', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<h3[^>]*>(.*?)</h3>', r'### \1\n', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<h[4-6][^>]*>(.*?)</h[4-6]>', r'#### \1\n', html, flags=re.DOTALL | re.IGNORECASE)
    
    # Convert paragraphs
    html = re.sub(r'<p[^>]*>(.*?)</p>', r'\1\n\n', html, flags=re.DOTALL | re.IGNORECASE)
    
    # Convert line breaks
    html = re.sub(r'<br[^>]*>', '\n', html, flags=re.IGNORECASE)
    
    # Convert links
    html = re.sub(r'<a[^>]*href=["\']([^"\']*)["\'][^>]*>(.*?)</a>', r'[\2](\1)', html, flags=re.DOTALL | re.IGNORECASE)
    
    # Remove all other HTML tags
    html = re.sub(r'<[^>]+>', '', html)
    
    # Decode HTML entities
    import html as html_module
    content = html_module.unescape(html)
    
    # Clean up whitespace
    content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)  # Multiple newlines to double
    content = re.sub(r' +', ' ', content)  # Multiple spaces to single
    
    return content.strip()


def html_to_text(html: str) -> str:
    """
    Convert HTML to plain text.
    Simple extraction that removes all HTML tags.
    
    Args:
        html: HTML content
        
    Returns:
        Plain text content
    """
    # Remove script and style elements completely
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
    
    # Convert line breaks and paragraphs to newlines
    html = re.sub(r'<br[^>]*>', '\n', html, flags=re.IGNORECASE)
    html = re.sub(r'<p[^>]*>', '\n', html, flags=re.IGNORECASE)
    html = re.sub(r'</p>', '\n', html, flags=re.IGNORECASE)
    
    # Remove all HTML tags
    html = re.sub(r'<[^>]+>', '', html)
    
    # Decode HTML entities
    import html as html_module
    content = html_module.unescape(html)
    
    # Clean up whitespace
    content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)
    content = re.sub(r' +', ' ', content)
    
    return content.strip()