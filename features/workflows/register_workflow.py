"""
Main registration workflow that orchestrates the entire data collection process.
This is the heavy lifting that happens asynchronously after /register returns.
"""

import logging
from typing import Dict, Any, Optional
from pathlib import Path
from datetime import datetime

from core.config import settings
from core.utils import (
    write_json, 
    generate_output_filename,
    ts,
    safe_url,
    create_processing_log_entry,
    calculate_processing_stats
)
import time
from features.website_analysis import discover, filter, scrape

logger = logging.getLogger(__name__)


async def execute_registration_workflow(data: Dict[str, Any], step) -> Dict[str, Any]:
    """
    Execute the main registration workflow.
    This is called by the Inngest function and handles all the async processing.
    
    Args:
        data: Event data containing registration information
        step: Inngest step function for creating checkpoints
    
    Returns:
        Dict with workflow results
    """
    request_id = data.get("request_id")
    timestamp = data.get("timestamp", ts())
    
    logger.info(f"Starting registration workflow for request {request_id}")
    
    # Extract input data
    input_data = {
        "first_name": data.get("first_name"),
        "last_name": data.get("last_name"),
        "company_website": data.get("company_website"),
        "linkedin": data.get("linkedin")
    }
    
    # Initialize result structure with enhanced metadata
    processing_start_time = time.time() * 1000  # milliseconds
    processing_log = []
    
    result = {
        "request_id": request_id,
        "timestamp": timestamp,
        "input_data": input_data,
        "linkedin_analysis": {
            "status": "not_implemented"
        },
        "website_analysis": {
            "discovered_urls": [],
            "filtered_urls": [],
            "scraped_content": []
        },
        "_processing_log": processing_log if settings.OUTPUT_DETAILED_LOGGING else None
    }
    
    try:
        # Process LinkedIn if provided
        if input_data.get("linkedin"):
            step_start = time.time() * 1000
            linkedin_result = await step.run(
                "analyze-linkedin",
                lambda: analyze_linkedin(input_data["linkedin"])
            )
            step_duration = int(time.time() * 1000 - step_start)
            
            result["linkedin_analysis"] = linkedin_result
            
            if settings.OUTPUT_DETAILED_LOGGING:
                processing_log.append(create_processing_log_entry(
                    "linkedin_analysis",
                    step_duration,
                    linkedin_result.get("status", "unknown")
                ))
        
        # Process company website if provided
        if input_data.get("company_website"):
            step_start = time.time() * 1000
            website_result = await step.run(
                "analyze-website",
                lambda: analyze_website(input_data["company_website"], processing_log)
            )
            step_duration = int(time.time() * 1000 - step_start)
            
            result["website_analysis"] = website_result
            
            if settings.OUTPUT_DETAILED_LOGGING:
                processing_log.append(create_processing_log_entry(
                    "website_analysis",
                    step_duration,
                    "success" if "error" not in website_result else "error"
                ))
        
        # Save results to JSON file
        await step.run(
            "save-results",
            lambda: save_workflow_results(result, request_id, processing_start_time, processing_log)
        )
        
        logger.info(f"Successfully completed workflow for request {request_id}")
        
    except Exception as e:
        logger.error(f"Workflow failed for request {request_id}: {e}", exc_info=True)
        
        # Save partial results even on failure
        result["error"] = {
            "message": str(e),
            "type": type(e).__name__,
            "timestamp": ts()
        }
        
        # Try to save what we have
        try:
            await save_workflow_results(result, request_id, processing_start_time, processing_log)
        except Exception as save_error:
            logger.error(f"Failed to save error results: {save_error}")
        
        raise  # Re-raise for Inngest retry
    
    return result


async def analyze_linkedin(linkedin_url: str) -> Dict[str, Any]:
    """
    Analyze LinkedIn profile.
    Currently returns not_implemented as per requirements.
    
    Implementation Plan (for README):
    1. Use a service like Proxycurl API (https://nubela.co/proxycurl/)
    2. Alternative: RapidAPI LinkedIn endpoints
    3. Alternative: Bright Data's LinkedIn dataset API
    
    These services typically provide:
    - Profile data (name, title, company, location)
    - Experience history
    - Education
    - Skills
    - Recent activity/posts
    
    Integration approach:
    - Add LINKEDIN_API_KEY to settings
    - Create linkedin_client.py similar to firecrawl_client.py
    - Parse profile URL to extract username/profile ID
    - Call API to get structured data
    - Extract relevant business intelligence
    
    Args:
        linkedin_url: LinkedIn profile URL
    
    Returns:
        Dict with LinkedIn analysis status
    """
    logger.info(f"LinkedIn analysis requested for {linkedin_url}")
    
    # For now, return not_implemented as required
    return {
        "status": "not_implemented",
        "url": linkedin_url,
        "implementation_plan": "See README.md for LinkedIn integration plan"
    }


async def analyze_website(website_url: str, processing_log: list = None) -> Dict[str, Any]:
    """
    Complete website analysis pipeline.
    Discovers URLs, filters for relevance, and scrapes content.
    
    Args:
        website_url: Company website URL
    
    Returns:
        Dict with website analysis results
    """
    logger.info(f"Starting website analysis for {website_url}")
    
    # Normalize the URL
    website_url = safe_url(website_url)
    if not website_url:
        logger.error(f"Invalid website URL provided: {website_url}")
        return {
            "discovered_urls": [],
            "filtered_urls": [],
            "scraped_content": [],
            "error": "Invalid URL"
        }
    
    result = {
        "discovered_urls": [],
        "filtered_urls": [],
        "scraped_content": []
    }
    
    try:
        # Phase 1: URL Discovery
        logger.info(f"Phase 1: Discovering URLs for {website_url}")
        discovery_start = time.time() * 1000
        discovery_result = await discover.discover_urls(website_url)
        discovery_duration = int(time.time() * 1000 - discovery_start)
        
        if processing_log is not None and settings.OUTPUT_DETAILED_LOGGING:
            processing_log.append(create_processing_log_entry(
                "url_discovery",
                discovery_duration,
                discovery_result["status"],
                urls_found=len(discovery_result.get("urls", []))
            ))
        
        if discovery_result["status"] != "success":
            logger.warning(f"URL discovery failed: {discovery_result}")
            # Still continue with just the main URL
            result["discovered_urls"] = [website_url]
            result["discovery_status"] = discovery_result["status"]
            result["discovery_reason"] = discovery_result.get("reason", "unknown")
        else:
            result["discovered_urls"] = discovery_result["urls"]
            logger.info(f"Discovered {len(result['discovered_urls'])} URLs")
        
        # Phase 2: Intelligent Filtering
        logger.info(f"Phase 2: Filtering {len(result['discovered_urls'])} URLs")
        filter_start = time.time() * 1000
        filter_result = await filter.filter_urls(
            result["discovered_urls"],
            base_url=website_url
        )
        filter_duration = int(time.time() * 1000 - filter_start)
        
        if processing_log is not None and settings.OUTPUT_DETAILED_LOGGING:
            processing_log.append(create_processing_log_entry(
                "url_filtering",
                filter_duration,
                "success",
                input_urls=len(result["discovered_urls"]),
                output_urls=len(filter_result["urls"])
            ))
        
        result["filtered_urls"] = filter_result["urls"]
        result["filter_reasons"] = filter_result.get("reasons", {})
        logger.info(f"Filtered to {len(result['filtered_urls'])} valuable URLs")
        
        # Phase 3: Content Scraping
        logger.info(f"Phase 3: Scraping {len(result['filtered_urls'])} URLs")
        scrape_start = time.time() * 1000
        scrape_result = await scrape.scrape_urls(result["filtered_urls"])
        scrape_duration = int(time.time() * 1000 - scrape_start)
        
        success_count = len([r for r in scrape_result["results"] if r["status"] == "success"])
        
        if processing_log is not None and settings.OUTPUT_DETAILED_LOGGING:
            processing_log.append(create_processing_log_entry(
                "content_scraping",
                scrape_duration,
                "success" if success_count > 0 else "partial",
                urls_scraped=len(result["filtered_urls"]),
                successful_scrapes=success_count,
                failed_scrapes=len(result["filtered_urls"]) - success_count
            ))
        
        # Format scraped content for output
        for item in scrape_result["results"]:
            content_entry = {
                "url": item["url"],
                "content": item.get("content", "")
            }
            
            # Add metadata if scraping failed
            if item["status"] != "success":
                content_entry["status"] = item["status"]
                content_entry["reason"] = item.get("reason", "unknown")
            
            result["scraped_content"].append(content_entry)
        
        # Add summary statistics
        result["statistics"] = {
            "total_discovered": len(result["discovered_urls"]),
            "total_filtered": len(result["filtered_urls"]),
            "total_scraped": len([s for s in scrape_result["results"] if s["status"] == "success"]),
            "scrape_failures": len([s for s in scrape_result["results"] if s["status"] != "success"])
        }
        
        logger.info(f"Website analysis complete: {result['statistics']}")
        
    except Exception as e:
        logger.error(f"Website analysis failed: {e}", exc_info=True)
        result["error"] = str(e)
    
    return result


async def save_workflow_results(
    result: Dict[str, Any], 
    request_id: str, 
    processing_start_time: float = None, 
    processing_log: list = None
) -> bool:
    """
    Save workflow results to JSON file in outputs directory with enhanced metadata.
    
    Args:
        result: Complete workflow results
        request_id: Request ID for filename generation
        processing_start_time: Start time in milliseconds (optional)
        processing_log: Detailed processing log (optional)
    
    Returns:
        bool: True if saved successfully
    """
    try:
        # Extract person name for filename
        input_data = result.get("input_data", {})
        first_name = input_data.get("first_name")
        last_name = input_data.get("last_name")
        
        # Generate enhanced filename
        filename = generate_output_filename(
            request_id, 
            first_name, 
            last_name
        )
        filepath = settings.OUTPUT_DIR / filename
        
        # Ensure the directory exists
        settings.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        
        # Calculate processing duration
        processing_end_time = time.time() * 1000
        processing_duration = (
            int(processing_end_time - processing_start_time) 
            if processing_start_time 
            else None
        )
        
        # Calculate content metrics
        website_analysis = result.get("website_analysis", {})
        content_bytes = sum(
            len(item.get("content", "")) 
            for item in website_analysis.get("scraped_content", [])
        )
        
        # Create enhanced metadata
        metadata = {
            "filename": filename,
            "person_name": f"{first_name} {last_name}" if first_name and last_name else None,
            "saved_at": ts(),
            "version": "1.1.0",
            "philosophy": "wars are won with logistics and propaganda"
        }
        
        # Add processing details if available
        if processing_start_time and settings.OUTPUT_DETAILED_LOGGING:
            metadata["processing"] = {
                "started_at": result.get("timestamp"),
                "completed_at": ts(),
                "duration_ms": processing_duration,
                "duration_seconds": round(processing_duration / 1000, 2) if processing_duration else None,
            }
            
            # Add processing statistics
            if processing_log:
                metadata["processing"]["steps"] = processing_log
                metadata["processing"]["statistics"] = calculate_processing_stats(processing_log)
        
        # Add resource usage statistics
        statistics = website_analysis.get("statistics", {})
        metadata["resources"] = {
            "content_bytes_scraped": content_bytes,
            "urls_discovered": statistics.get("total_discovered", 0),
            "urls_filtered": statistics.get("total_filtered", 0),
            "urls_scraped": statistics.get("total_scraped", 0),
            "scrape_success_rate": (
                round(statistics.get("total_scraped", 0) / max(statistics.get("total_filtered", 1), 1) * 100, 1)
                if statistics.get("total_filtered", 0) > 0 else 0
            )
        }
        
        result["_metadata"] = metadata
        
        # Write to file
        success = write_json(filepath, result)
        
        if success:
            logger.info(f"Saved results to {filepath}")
        else:
            logger.error(f"Failed to save results to {filepath}")
        
        return success
        
    except Exception as e:
        logger.error(f"Error saving workflow results: {e}", exc_info=True)
        return False


# Alternative synchronous version for testing without Inngest
async def execute_registration_workflow_sync(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Synchronous version of the workflow for testing without Inngest.
    This bypasses the step function and runs everything directly.
    
    Args:
        data: Registration data
    
    Returns:
        Dict with workflow results
    """
    logger.info("Running workflow in synchronous mode (testing)")
    
    # Create a mock step function that just executes immediately
    class MockStep:
        async def run(self, name: str, func):
            logger.debug(f"Mock step: {name}")
            result = func()
            if hasattr(result, '__await__'):
                return await result
            return result
    
    return await execute_registration_workflow(data, MockStep())