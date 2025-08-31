"""
URL filtering module - Phase 2 of website analysis.
Intelligently filters discovered URLs to keep only business-relevant ones.
"""

import logging
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse
import re

from core.config import settings
from core.utils import extract_domain, is_same_domain

logger = logging.getLogger(__name__)


async def filter_urls(
    urls: List[str],
    base_url: Optional[str] = None,
    max_urls: Optional[int] = None
) -> Dict[str, Any]:
    """
    Intelligently filter URLs to keep only business-relevant ones.
    
    We're an AI company, so we solve this filtering problem intelligently.
    Considers: What makes a URL valuable for business intelligence?
    
    Args:
        urls: List of discovered URLs
        base_url: Original base URL for domain checking
        max_urls: Maximum URLs to keep (default from settings)
    
    Returns:
        Dict with filtered URLs and filtering reasons
    """
    max_urls = max_urls or settings.BI_URL_LIMIT
    
    logger.info(f"Filtering {len(urls)} URLs to max {max_urls} business-relevant URLs")
    
    if not urls:
        return {
            "urls": [],
            "reasons": {},
            "stats": {"input": 0, "output": 0}
        }
    
    # Score each URL
    scored_urls = []
    reasons = {}
    
    for url in urls:
        score, reason = score_url_value(url, base_url)
        scored_urls.append((url, score))
        reasons[url] = reason
    
    # Sort by score (higher is better)
    scored_urls.sort(key=lambda x: x[1], reverse=True)
    
    # Take top URLs
    filtered_urls = [url for url, score in scored_urls[:max_urls] if score > 0]
    
    # Log filtering results
    logger.info(f"Filtered from {len(urls)} to {len(filtered_urls)} URLs")
    
    # Log top filtered URLs
    for i, (url, score) in enumerate(scored_urls[:max_urls]):
        if score > 0:
            logger.debug(f"  [{i+1}] Score {score}: {url}")
    
    # Create result
    result = {
        "urls": filtered_urls,
        "reasons": {url: reasons[url] for url in filtered_urls},
        "stats": {
            "input": len(urls),
            "output": len(filtered_urls),
            "filtered_out": len(urls) - len(filtered_urls)
        }
    }
    
    # Add debug info about what was filtered out
    filtered_out = [url for url, score in scored_urls[max_urls:] if score > 0]
    if filtered_out:
        result["filtered_out_samples"] = filtered_out[:5]  # Show first 5 that didn't make it
    
    return result


def score_url_value(url: str, base_url: Optional[str] = None) -> tuple[int, str]:
    """
    Score a URL based on its potential business intelligence value.
    Higher score = more valuable for understanding the company.
    
    Scoring logic:
    - High value paths (about, team, services): +10 points
    - Medium value paths (blog, resources): +5 points  
    - Low value/excluded paths: -10 points
    - File extensions: varies by type
    - URL depth and structure: varies
    
    Args:
        url: URL to score
        base_url: Base URL for domain comparison
    
    Returns:
        Tuple of (score, reason)
    """
    score = 0
    reasons = []
    
    # Parse URL
    parsed = urlparse(url.lower())
    path = parsed.path.lower()
    
    # Check if same domain (if base_url provided)
    if base_url and not is_same_domain(url, base_url):
        return (-100, "different_domain")
    
    # High-value paths from settings
    valuable_paths = settings.valuable_paths_list
    for valuable in valuable_paths:
        if valuable in path:
            score += 10
            reasons.append(f"contains_{valuable}")
            break  # Only count once
    
    # Excluded paths from settings
    excluded_paths = settings.excluded_paths_list
    for excluded in excluded_paths:
        if excluded in path:
            score -= 10
            reasons.append(f"excluded_{excluded}")
    
    # Check for specific high-value patterns
    high_value_patterns = [
        (r'/about[-_]?us', 15, "about_us_page"),
        (r'/our[-_]?team', 15, "team_page"),
        (r'/leadership', 15, "leadership_page"),
        (r'/case[-_]?stud', 12, "case_studies"),
        (r'/portfolio', 12, "portfolio"),
        (r'/services?', 10, "services"),
        (r'/solutions?', 10, "solutions"),
        (r'/products?', 10, "products"),
        (r'/customers?', 10, "customers"),
        (r'/clients?', 10, "clients"),
        (r'/testimonials?', 8, "testimonials"),
        (r'/mission', 8, "mission"),
        (r'/values?', 8, "values"),
        (r'/culture', 8, "culture"),
        (r'/blog/', 5, "blog_post"),
        (r'/insights?/', 5, "insights"),
        (r'/20\d{2}/', 3, "dated_content"),  # Year in URL
    ]
    
    for pattern, points, reason in high_value_patterns:
        if re.search(pattern, path):
            score += points
            reasons.append(reason)
            break  # Only match first pattern
    
    # Check for low-value patterns
    low_value_patterns = [
        (r'/tag/', -5, "tag_page"),
        (r'/category/', -5, "category_page"),
        (r'/page/\d+', -5, "pagination"),
        (r'/search', -10, "search_page"),
        (r'/login', -10, "login_page"),
        (r'/signup', -10, "signup_page"),
        (r'/register', -10, "register_page"),
        (r'/cart', -10, "cart_page"),
        (r'/checkout', -10, "checkout_page"),
        (r'\.pdf$', -3, "pdf_file"),  # PDFs are hard to parse
        (r'\.(jpg|jpeg|png|gif|svg)$', -10, "image_file"),
        (r'\.(css|js)$', -20, "asset_file"),
        (r'/wp-', -5, "wordpress_internal"),
        (r'/feed', -10, "feed_url"),
        (r'/rss', -10, "rss_url"),
        (r'#', -5, "has_fragment"),
        (r'\?', -2, "has_query_params"),
    ]
    
    for pattern, points, reason in low_value_patterns:
        if re.search(pattern, path):
            score += points
            reasons.append(reason)
    
    # Check URL depth (prefer not too deep)
    depth = path.count('/')
    if depth > 4:
        score -= 2
        reasons.append("deep_url")
    elif depth <= 2:
        score += 2
        reasons.append("shallow_url")
    
    # Check URL length (prefer shorter)
    if len(url) > 150:
        score -= 3
        reasons.append("very_long_url")
    elif len(url) < 50:
        score += 1
        reasons.append("short_url")
    
    # Homepage gets bonus
    if path in ['/', '/index', '/index.html', '/home']:
        score += 5
        reasons.append("homepage")
    
    # Join reasons into string
    reason_str = ", ".join(reasons) if reasons else "no_special_markers"
    
    return (score, reason_str)


def get_url_category(url: str) -> str:
    """
    Categorize a URL for better organization.
    
    Args:
        url: URL to categorize
    
    Returns:
        Category string
    """
    path = urlparse(url.lower()).path.lower()
    
    # Category mappings
    categories = {
        "company_info": ['about', 'mission', 'vision', 'values', 'culture', 'history'],
        "team": ['team', 'leadership', 'executive', 'founder', 'board', 'advisor'],
        "offerings": ['service', 'solution', 'product', 'offering', 'feature'],
        "evidence": ['case', 'study', 'portfolio', 'work', 'project', 'client', 'customer'],
        "content": ['blog', 'article', 'post', 'news', 'insight', 'resource'],
        "contact": ['contact', 'location', 'office'],
        "careers": ['career', 'job', 'hiring', 'recruit'],
        "legal": ['privacy', 'terms', 'legal', 'cookie', 'gdpr'],
        "technical": ['api', 'docs', 'documentation', 'developer'],
    }
    
    for category, keywords in categories.items():
        for keyword in keywords:
            if keyword in path:
                return category
    
    return "other"


def deduplicate_similar_urls(urls: List[str]) -> List[str]:
    """
    Remove near-duplicate URLs (e.g., with/without trailing slash, http/https).
    
    Args:
        urls: List of URLs
    
    Returns:
        Deduplicated list
    """
    seen_normalized = set()
    unique_urls = []
    
    for url in urls:
        # Normalize for comparison
        normalized = url.lower().rstrip('/').replace('https://', 'http://')
        normalized = normalized.split('?')[0].split('#')[0]  # Remove query and fragment
        
        if normalized not in seen_normalized:
            seen_normalized.add(normalized)
            unique_urls.append(url)
    
    return unique_urls