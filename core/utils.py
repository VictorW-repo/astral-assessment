"""
Utility functions for the application
Provides common helpers for timestamps, IDs, file operations, and URL handling
"""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse, urlunparse
import re
import logging

logger = logging.getLogger(__name__)


def ts() -> str:
    """
    Generate an ISO format timestamp in UTC.
    Used consistently throughout the application.
    """
    return datetime.now(timezone.utc).isoformat()


def uid() -> str:
    """
    Generate a unique identifier (UUID4).
    Used for request IDs and other unique identifiers.
    """
    return str(uuid.uuid4())


def write_json(filepath: Path, data: Dict[str, Any], indent: int = 2) -> bool:
    """
    Write data to a JSON file with proper error handling.
    
    Args:
        filepath: Path to write the JSON file
        data: Dictionary to serialize to JSON
        indent: JSON indentation level (default 2)
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Ensure parent directory exists
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        # Write with atomic operation (write to temp, then rename)
        temp_path = filepath.with_suffix('.tmp')
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=indent, ensure_ascii=False, default=str)
        
        # Atomic rename
        temp_path.replace(filepath)
        
        logger.info(f"Successfully wrote JSON to {filepath}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to write JSON to {filepath}: {e}")
        return False


def read_json(filepath: Path) -> Optional[Dict[str, Any]]:
    """
    Read and parse a JSON file.
    
    Args:
        filepath: Path to the JSON file
    
    Returns:
        Parsed JSON data or None if failed
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning(f"JSON file not found: {filepath}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in {filepath}: {e}")
        return None
    except Exception as e:
        logger.error(f"Failed to read JSON from {filepath}: {e}")
        return None


def ensure_dir(directory: Path) -> bool:
    """
    Ensure a directory exists, creating it if necessary.
    
    Args:
        directory: Path to the directory
    
    Returns:
        bool: True if directory exists or was created successfully
    """
    try:
        directory.mkdir(parents=True, exist_ok=True)
        return True
    except Exception as e:
        logger.error(f"Failed to create directory {directory}: {e}")
        return False


def safe_url(url: Optional[str]) -> Optional[str]:
    """
    Safely normalize and validate a URL.
    Adds https:// if no scheme is present.
    
    Args:
        url: URL string to normalize
    
    Returns:
        Normalized URL or None if invalid
    """
    if not url:
        return None
    
    url = url.strip()
    if not url:
        return None
    
    try:
        # Add https:// if no scheme
        if not url.startswith(('http://', 'https://')):
            url = f'https://{url}'
        
        # Parse and validate
        parsed = urlparse(url)
        
        # Ensure we have at least a netloc
        if not parsed.netloc:
            logger.warning(f"Invalid URL (no netloc): {url}")
            return None
        
        # Reconstruct URL (this normalizes it)
        normalized = urlunparse(parsed)
        
        return normalized
        
    except Exception as e:
        logger.warning(f"Failed to normalize URL {url}: {e}")
        return None


def extract_domain(url: str) -> Optional[str]:
    """
    Extract the domain from a URL.
    
    Args:
        url: URL to extract domain from
    
    Returns:
        Domain string or None if failed
    """
    try:
        parsed = urlparse(url)
        return parsed.netloc.lower()
    except Exception as e:
        logger.warning(f"Failed to extract domain from {url}: {e}")
        return None


def is_same_domain(url1: str, url2: str) -> bool:
    """
    Check if two URLs are from the same domain.
    
    Args:
        url1: First URL
        url2: Second URL
    
    Returns:
        bool: True if same domain
    """
    domain1 = extract_domain(url1)
    domain2 = extract_domain(url2)
    
    if not domain1 or not domain2:
        return False
    
    # Handle www subdomain
    domain1 = domain1.replace('www.', '')
    domain2 = domain2.replace('www.', '')
    
    return domain1 == domain2


def generate_output_filename(request_id: str) -> str:
    """
    Generate a filename for the output JSON file.
    Format: analysis_YYYYMMDD_HHMMSS_<request_id>.json
    
    Args:
        request_id: Unique request identifier
    
    Returns:
        str: Generated filename
    """
    now = datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    
    # Sanitize request_id (remove any problematic characters)
    safe_id = re.sub(r'[^a-zA-Z0-9\-_]', '', request_id)[:8]  # Keep first 8 chars
    
    return f"analysis_{timestamp}_{safe_id}.json"


def truncate_text(text: str, max_length: int = 1000, suffix: str = "...") -> str:
    """
    Truncate text to a maximum length, adding suffix if truncated.
    
    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated
    
    Returns:
        str: Truncated text
    """
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix


def clean_text(text: str) -> str:
    """
    Clean text by removing excessive whitespace and special characters.
    Useful for processing scraped content.
    
    Args:
        text: Text to clean
    
    Returns:
        str: Cleaned text
    """
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text)
    
    # Remove control characters
    text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)
    
    # Trim
    text = text.strip()
    
    return text


def format_bytes(bytes_value: int) -> str:
    """
    Format bytes into human-readable string.
    
    Args:
        bytes_value: Number of bytes
    
    Returns:
        str: Formatted string (e.g., "1.5 MB")
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.2f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.2f} PB"


def is_valid_url(url: str) -> bool:
    """
    Check if a URL is valid and accessible (basic validation).
    
    Args:
        url: URL to validate
    
    Returns:
        bool: True if valid
    """
    if not url:
        return False
    
    try:
        parsed = urlparse(url)
        return bool(parsed.netloc) and parsed.scheme in ('http', 'https')
    except Exception:
        return False