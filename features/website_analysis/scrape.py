"""
URL scraping module - Phase 3 of website analysis.
Extracts content from filtered URLs using Firecrawl.
"""

import logging
from typing import List, Dict, Any, Optional
import asyncio

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
    
    # Use Firecrawl batch scraping with concurrency control
    scrape_results = await firecrawl.batch_scrape(urls, format=format)
    
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