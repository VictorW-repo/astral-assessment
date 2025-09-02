"""
Human-readable error messages for API and processing errors.
Maps technical error codes to user-friendly descriptions with actionable guidance.
"""

from typing import Dict, List, Optional, Tuple


# Error messages mapping technical codes to human-readable descriptions
ERROR_MESSAGES: Dict[str, Dict[str, str]] = {
    # HTTP Status Code Errors - Payment & Credits
    "http_402": {
        "message": "API credits exhausted. Please add credits to your Firecrawl account to continue web scraping.",
        "category": "payment",
        "action": "add_credits",
        "severity": "high"
    },
    "http_429": {
        "message": "Rate limit exceeded. The API is temporarily throttling requests to prevent overload.",
        "category": "rate_limit", 
        "action": "wait_and_retry",
        "severity": "medium"
    },
    
    # HTTP Status Code Errors - Server Issues
    "http_408": {
        "message": "Request timeout. The server took too long to respond, possibly due to high load or rate limiting.",
        "category": "timeout",
        "action": "wait_and_retry", 
        "severity": "medium"
    },
    "http_500": {
        "message": "Internal server error. The API service is experiencing technical difficulties.",
        "category": "server_error",
        "action": "contact_support",
        "severity": "high"
    },
    "http_502": {
        "message": "Bad gateway. The API service is temporarily unavailable.",
        "category": "server_error", 
        "action": "wait_and_retry",
        "severity": "medium"
    },
    "http_503": {
        "message": "Service unavailable. The API is temporarily down for maintenance.",
        "category": "server_error",
        "action": "wait_and_retry", 
        "severity": "medium"
    },
    "http_504": {
        "message": "Gateway timeout. The API service is not responding.",
        "category": "server_error",
        "action": "wait_and_retry",
        "severity": "medium"
    },
    
    # HTTP Status Code Errors - Client Issues  
    "http_401": {
        "message": "Authentication failed. Check your API key configuration.",
        "category": "authentication",
        "action": "check_api_key",
        "severity": "high"
    },
    "http_403": {
        "message": "Access forbidden. Your API key may lack required permissions.",
        "category": "authorization",
        "action": "check_permissions", 
        "severity": "high"
    },
    "http_404": {
        "message": "URL not found. The requested resource could not be located.",
        "category": "not_found",
        "action": "check_url",
        "severity": "low"
    },
    
    # Circuit Breaker & Connection Errors
    "circuit_breaker_open": {
        "message": "Circuit breaker activated due to repeated API failures. Service is temporarily paused to prevent further errors.",
        "category": "circuit_breaker",
        "action": "wait_and_retry",
        "severity": "high"
    },
    "request_timeout": {
        "message": "Request timeout after multiple retries. The service may be overloaded or experiencing issues.",
        "category": "timeout", 
        "action": "wait_and_retry",
        "severity": "medium"
    },
    "http_error": {
        "message": "Network or HTTP communication error occurred during the request.",
        "category": "network",
        "action": "check_connection",
        "severity": "medium"  
    },
    
    # API Service Errors
    "no_api_key": {
        "message": "No API key provided. Running in fallback mode with limited functionality.",
        "category": "configuration",
        "action": "add_api_key",
        "severity": "low"
    },
    "invalid_url": {
        "message": "The provided URL is invalid or malformed.",
        "category": "validation",
        "action": "check_url",
        "severity": "low"
    },
    
    # Processing Errors
    "skipped": {
        "message": "Operation skipped due to missing configuration or API key.",
        "category": "configuration", 
        "action": "check_configuration",
        "severity": "low"
    },
    
    # Crawl Job Errors
    "crawl_failed": {
        "message": "Crawl job failed to complete. The website may be inaccessible or have restrictions.",
        "category": "crawl_error",
        "action": "check_url",
        "severity": "medium"
    },
    "crawl_timeout": {
        "message": "Crawl job timed out. The website may be very large or slow to respond.",
        "category": "timeout",
        "action": "wait_and_retry",
        "severity": "medium"
    },
    "no_job_id": {
        "message": "Failed to start crawl job. API may be experiencing issues.",
        "category": "api_error", 
        "action": "contact_support",
        "severity": "high"
    }
}

# Action guidance for users
ACTION_GUIDANCE: Dict[str, Dict[str, str]] = {
    "add_credits": {
        "title": "Add API Credits",
        "description": "Purchase additional API credits from your Firecrawl dashboard",
        "url": "https://firecrawl.dev/dashboard"
    },
    "wait_and_retry": {
        "title": "Wait and Retry",
        "description": "Wait a few minutes before trying again to allow the service to recover",
        "url": None
    },
    "contact_support": {
        "title": "Contact Support", 
        "description": "Reach out to API support if the issue persists",
        "url": "https://firecrawl.dev/support"
    },
    "check_api_key": {
        "title": "Check API Key",
        "description": "Verify your API key is correct in the .env file", 
        "url": None
    },
    "check_permissions": {
        "title": "Check Permissions",
        "description": "Ensure your API key has the required permissions for this operation",
        "url": None
    },
    "check_url": {
        "title": "Check URL",
        "description": "Verify the URL is correct, accessible, and properly formatted",
        "url": None
    },
    "add_api_key": {
        "title": "Add API Key", 
        "description": "Add your Firecrawl API key to the .env file for full functionality",
        "url": "https://firecrawl.dev/dashboard"
    },
    "check_configuration": {
        "title": "Check Configuration",
        "description": "Verify all required configuration settings are properly set",
        "url": None
    },
    "check_connection": {
        "title": "Check Connection",
        "description": "Verify your internet connection and network settings",
        "url": None
    }
}

# Severity levels for error categorization
SEVERITY_LEVELS = {
    "low": {"priority": 1, "description": "Minor issue, operation can continue"},
    "medium": {"priority": 2, "description": "Significant issue, some functionality affected"},
    "high": {"priority": 3, "description": "Critical issue, major functionality impacted"}
}


def get_human_readable_error(error_code: str) -> Optional[Dict[str, str]]:
    """
    Get human-readable error information for a technical error code.
    
    Args:
        error_code: Technical error code (e.g., 'http_402', 'circuit_breaker_open')
    
    Returns:
        Dict with human-readable error information or None if code not found
    """
    return ERROR_MESSAGES.get(error_code)


def get_action_guidance(action_code: str) -> Optional[Dict[str, str]]:
    """
    Get action guidance for a specific action code.
    
    Args:
        action_code: Action code from error message (e.g., 'add_credits')
    
    Returns:
        Dict with action guidance or None if code not found
    """
    return ACTION_GUIDANCE.get(action_code)


def format_error_message(error_code: str, include_action: bool = True) -> str:
    """
    Format a complete error message with optional action guidance.
    
    Args:
        error_code: Technical error code
        include_action: Whether to include action guidance in the message
    
    Returns:
        Formatted error message string
    """
    error_info = get_human_readable_error(error_code)
    if not error_info:
        return f"Unknown error: {error_code}"
    
    message = error_info["message"]
    
    if include_action and "action" in error_info:
        action_info = get_action_guidance(error_info["action"])
        if action_info:
            message += f" {action_info['description']}."
    
    return message


def categorize_errors(error_codes: List[str]) -> Dict[str, List[str]]:
    """
    Categorize a list of error codes by their type.
    
    Args:
        error_codes: List of technical error codes
    
    Returns:
        Dict mapping categories to lists of error codes
    """
    categories = {}
    
    for code in error_codes:
        error_info = get_human_readable_error(code)
        if error_info:
            category = error_info.get("category", "unknown")
            if category not in categories:
                categories[category] = []
            categories[category].append(code)
    
    return categories


def get_severity_level(error_code: str) -> Tuple[str, int]:
    """
    Get severity level and priority for an error code.
    
    Args:
        error_code: Technical error code
    
    Returns:
        Tuple of (severity_name, priority_number)
    """
    error_info = get_human_readable_error(error_code)
    if not error_info:
        return "medium", 2
    
    severity = error_info.get("severity", "medium")
    priority = SEVERITY_LEVELS.get(severity, SEVERITY_LEVELS["medium"])["priority"]
    
    return severity, priority


def create_error_summary(error_codes: List[str]) -> Dict[str, any]:
    """
    Create a comprehensive error summary from a list of error codes.
    
    Args:
        error_codes: List of technical error codes encountered
    
    Returns:
        Dict with error summary information
    """
    if not error_codes:
        return {"has_errors": False}
    
    categories = categorize_errors(error_codes)
    
    # Check for payment-related issues
    has_payment_issues = bool(set(error_codes) & {"http_402", "http_401", "http_403"})
    payment_errors = [code for code in error_codes if code in {"http_402", "http_401", "http_403"}]
    
    # Check for rate limiting issues
    has_rate_limit_issues = bool(set(error_codes) & {"http_429", "http_408", "request_timeout"})
    rate_limit_errors = [code for code in error_codes if code in {"http_429", "http_408", "request_timeout"}]
    
    # Get highest severity
    severities = [get_severity_level(code) for code in error_codes]
    max_severity = max(severities, key=lambda x: x[1]) if severities else ("low", 1)
    
    # Collect unique actions
    actions = set()
    for code in error_codes:
        error_info = get_human_readable_error(code)
        if error_info and "action" in error_info:
            actions.add(error_info["action"])
    
    # Create user message
    user_message = _generate_user_message(categories, has_payment_issues, has_rate_limit_issues)
    
    return {
        "has_errors": True,
        "total_errors": len(error_codes),
        "error_codes": error_codes,
        "categories": categories,
        "has_payment_issues": has_payment_issues,
        "payment_errors": payment_errors,
        "has_rate_limit_issues": has_rate_limit_issues,
        "rate_limit_errors": rate_limit_errors,
        "max_severity": max_severity[0],
        "max_priority": max_severity[1],
        "recommended_actions": list(actions),
        "user_message": user_message
    }


def _generate_user_message(categories: Dict[str, List[str]], has_payment: bool, has_rate_limit: bool) -> str:
    """
    Generate a user-friendly summary message based on error categories.
    
    Args:
        categories: Categorized errors
        has_payment: Whether payment errors are present
        has_rate_limit: Whether rate limit errors are present
    
    Returns:
        User-friendly summary message
    """
    if has_payment:
        return "Some operations failed due to API credit exhaustion or authentication issues. Please check your API credits and key configuration."
    elif has_rate_limit:
        return "Some operations were rate limited or timed out. The API may be experiencing high load. Please wait and retry."
    elif "server_error" in categories:
        return "Some operations failed due to server issues. The API service may be experiencing technical difficulties."
    elif "configuration" in categories:
        return "Some operations were skipped due to missing configuration. Please check your API key and settings."
    else:
        return f"Some operations encountered errors in the following areas: {', '.join(categories.keys())}."