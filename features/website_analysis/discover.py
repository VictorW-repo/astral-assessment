"""
URL discovery module - Phase 1 of website analysis.
Discovers all URLs within a company website using Firecrawl.
"""

import logging
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse, urljoin
import re

from core.clients import firecrawl
from core.config import settings
from core.utils import safe_url, extract_domain, is_same_domain

logger = logging.getLogger(__name__)


async def discover_urls(
    website_url: str,
    max_urls: Optional[int] = None
) -> Dict[str, Any]:
    """
    Discover URLs from a company website.
    Uses Firecrawl's crawl/map functionality to find all pages.
    
    Targets pages like:
    - about-us, our-approach, team, leadership
    - services, solutions, products
    - case-studies, portfolio, clients
    - blog posts about company culture
    - investor relations
    - external links to their LinkedIn
    
    Args:
        website_url: Starting URL to crawl
        max_urls: Maximum number of URLs to discover (default from settings)
    
    Returns:
        Dict containing status and discovered URLs
    """
    max_urls = max_urls or settings.FIRECRAWL_MAX_URLS
    
    logger.info(f"Starting URL discovery for {website_url} (max: {max_urls})")
    
    # Normalize URL
    website_url = safe_url(website_url)
    if not website_url:
        return {
            "status": "error",
            "reason": "invalid_url",
            "urls": []
        }
    
    # Get base domain for filtering
    base_domain = extract_domain(website_url)
    
    try:
        # Use Firecrawl to crawl the website
        crawl_result = await firecrawl.crawl(website_url, limit=max_urls)
        
        # Handle different response statuses
        if crawl_result["status"] == "skipped":
            # No API key - try alternative discovery methods
            logger.info("No Firecrawl API key - using fallback discovery")
            return await discover_urls_fallback(website_url)
        
        if crawl_result["status"] == "rate_limited":
            logger.warning("Rate limited - returning minimal URLs")
            return {
                "status": "rate_limited",
                "reason": crawl_result.get("reason", "rate_limit"),
                "urls": [website_url]
            }
        
        if crawl_result["status"] != "success":
            logger.error(f"Crawl failed: {crawl_result}")
            return {
                "status": crawl_result["status"],
                "reason": crawl_result.get("reason", "unknown"),
                "urls": [website_url]
            }
        
        # Process discovered URLs
        discovered_urls = crawl_result.get("urls", [])
        
        # Filter to same domain and clean up
        filtered_urls = []
        for url in discovered_urls:
            # Ensure it's a valid URL
            clean_url = safe_url(url)
            if not clean_url:
                continue
            
            # Check if same domain
            if is_same_domain(clean_url, website_url):
                filtered_urls.append(clean_url)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_urls = []
        for url in filtered_urls:
            # Normalize by removing trailing slashes and fragments
            normalized = url.rstrip('/').split('#')[0]
            if normalized not in seen:
                seen.add(normalized)
                unique_urls.append(url)
        
        logger.info(f"Discovered {len(unique_urls)} unique URLs on {base_domain}")
        
        return {
            "status": "success",
            "urls": unique_urls[:max_urls],  # Respect max limit
            "total_found": len(unique_urls),
            "domain": base_domain
        }
        
    except Exception as e:
        logger.error(f"Error discovering URLs: {e}", exc_info=True)
        return {
            "status": "error",
            "reason": str(e),
            "urls": [website_url]
        }


async def discover_urls_fallback(website_url: str) -> Dict[str, Any]:
    """
    Fallback URL discovery when Firecrawl is not available.
    Generates common URL patterns to check.
    
    Args:
        website_url: Base website URL
    
    Returns:
        Dict with discovered URLs using common patterns
    """
    logger.info("Using fallback URL discovery with common patterns")
    
    # Parse base URL
    parsed = urlparse(website_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    
    # Common URL patterns for business websites
    common_paths = [
        "",  # Homepage
        "/about",
        "/about-us",
        "/our-story",
        "/mission",
        "/team",
        "/leadership",
        "/our-team",
        "/services",
        "/solutions",
        "/products",
        "/what-we-do",
        "/case-studies",
        "/portfolio",
        "/our-work",
        "/clients",
        "/customers",
        "/testimonials",
        "/blog",
        "/news",
        "/insights",
        "/resources",
        "/contact",
        "/contact-us",
        "/careers",
        "/jobs",
        "/investors",
        "/investor-relations",
        "/press",
        "/media",
    ]
    
    # Generate URLs
    discovered_urls = []
    for path in common_paths:
        url = urljoin(base, path)
        discovered_urls.append(url)
    
    # Also try with .html extensions
    html_paths = ["/index.html", "/about.html", "/services.html", "/contact.html"]
    for path in html_paths:
        url = urljoin(base, path)
        discovered_urls.append(url)
    
    # Remove duplicates
    discovered_urls = list(dict.fromkeys(discovered_urls))
    
    logger.info(f"Generated {len(discovered_urls)} fallback URLs")
    
    return {
        "status": "success",
        "urls": discovered_urls,
        "total_found": len(discovered_urls),
        "method": "fallback_patterns",
        "note": "URLs generated from common patterns - not all may exist"
    }


def extract_sitemap_hints(base_url: str) -> List[str]:
    """
    Generate potential sitemap URLs for a website.
    
    Args:
        base_url: Base website URL
    
    Returns:
        List of potential sitemap URLs
    """
    parsed = urlparse(base_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    
    sitemap_urls = [
        urljoin(base, "/sitemap.xml"),
        urljoin(base, "/sitemap_index.xml"),
        urljoin(base, "/sitemap"),
        urljoin(base, "/robots.txt"),  # Often contains sitemap location
    ]
    
    return sitemap_urls


def is_valuable_discovery_url(url: str) -> bool:
    """
    Quick check if a URL is potentially valuable for discovery.
    Used during the discovery phase to prioritize URLs.
    
    Args:
        url: URL to check
    
    Returns:
        bool: True if URL seems valuable
    """
    # Parse URL
    parsed = urlparse(url.lower())
    path = parsed.path.lower()
    
    # High-value indicators
    valuable_keywords = [
        'about', 'team', 'leadership', 'executive',
        'service', 'solution', 'product', 'offering',
        'case', 'study', 'portfolio', 'work', 'project',
        'client', 'customer', 'testimonial', 'review',
        'mission', 'vision', 'value', 'culture',
        'investor', 'relation', 'financial',
        'blog', 'insight', 'resource', 'whitepaper'
    ]
    
    # Check if path contains valuable keywords
    for keyword in valuable_keywords:
        if keyword in path:
            return True
    
    # Check for year patterns (might be blog posts)
    if re.search(r'/20\d{2}/', path):
        return True
    
    return False