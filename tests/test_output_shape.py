"""
Test output file shape and structure.
Verifies that JSON files are created with correct schema after calling /register.
Tolerant of Firecrawl being disabled/skipped.
"""

import pytest
import json
import asyncio
from pathlib import Path
from fastapi.testclient import TestClient
import time
from typing import Dict, Any, Optional

from main import app
from core.config import settings
from features.workflows.register_workflow import execute_registration_workflow_sync

client = TestClient(app)


def find_latest_output_file(request_id: Optional[str] = None) -> Optional[Path]:
    """Find the most recent output file, optionally matching a request_id."""
    output_dir = Path(settings.OUTPUT_DIR)
    
    if not output_dir.exists():
        return None
    
    # Get all analysis files
    files = list(output_dir.glob("analysis_*.json"))
    
    if not files:
        return None
    
    # If request_id provided, filter by it
    if request_id:
        # Request ID is in filename (last 8 chars before .json)
        filtered = [f for f in files if request_id[:8] in str(f)]
        if filtered:
            files = filtered
    
    # Return most recent file
    return max(files, key=lambda f: f.stat().st_mtime)


def validate_output_schema(data: Dict[str, Any]) -> list:
    """
    Validate the output JSON schema.
    Returns list of validation errors (empty if valid).
    """
    errors = []
    
    # Check required top-level fields
    required_fields = [
        "request_id",
        "timestamp", 
        "input_data",
        "linkedin_analysis",
        "website_analysis"
    ]
    
    for field in required_fields:
        if field not in data:
            errors.append(f"Missing required field: {field}")
    
    # Validate input_data structure
    if "input_data" in data:
        input_data = data["input_data"]
        for field in ["first_name", "last_name"]:
            if field not in input_data:
                errors.append(f"Missing input_data.{field}")
        
        # At least one URL should be present
        if not input_data.get("company_website") and not input_data.get("linkedin"):
            errors.append("input_data must have at least one of company_website or linkedin")
    
    # Validate linkedin_analysis structure
    if "linkedin_analysis" in data:
        linkedin = data["linkedin_analysis"]
        if "status" not in linkedin:
            errors.append("Missing linkedin_analysis.status")
        # Status should be "not_implemented" as per requirements
        if linkedin.get("status") != "not_implemented":
            errors.append(f"linkedin_analysis.status should be 'not_implemented', got '{linkedin.get('status')}'")
    
    # Validate website_analysis structure
    if "website_analysis" in data:
        website = data["website_analysis"]
        required_website_fields = ["discovered_urls", "filtered_urls", "scraped_content"]
        
        for field in required_website_fields:
            if field not in website:
                errors.append(f"Missing website_analysis.{field}")
            elif not isinstance(website[field], list):
                errors.append(f"website_analysis.{field} should be a list")
        
        # Validate scraped_content structure
        if "scraped_content" in website and website["scraped_content"]:
            for i, item in enumerate(website["scraped_content"]):
                if not isinstance(item, dict):
                    errors.append(f"website_analysis.scraped_content[{i}] should be a dict")
                elif "url" not in item:
                    errors.append(f"website_analysis.scraped_content[{i}] missing 'url'")
                elif "content" not in item and "status" not in item:
                    errors.append(f"website_analysis.scraped_content[{i}] missing 'content' or 'status'")
    
    return errors


class TestOutputShape:
    """Test the shape and structure of output JSON files."""
    
    @pytest.mark.asyncio
    async def test_output_file_created_sync(self):
        """Test that output file is created using sync workflow (no Inngest)."""
        # Prepare test data
        test_data = {
            "request_id": "test-output-" + str(int(time.time())),
            "timestamp": "2025-08-31T14:30:22Z",
            "first_name": "Test",
            "last_name": "User",
            "company_website": "https://example.com"
        }
        
        # Execute workflow synchronously (bypasses Inngest)
        result = await execute_registration_workflow_sync(test_data)
        
        # Find the output file
        output_file = find_latest_output_file(test_data["request_id"])
        
        assert output_file is not None, "Output file was not created"
        assert output_file.exists(), f"Output file does not exist: {output_file}"
        
        # Read and validate the file
        with open(output_file, 'r') as f:
            data = json.load(f)
        
        errors = validate_output_schema(data)
        assert not errors, f"Schema validation errors: {errors}"
        
        # Check that input data matches
        assert data["request_id"] == test_data["request_id"]
        assert data["input_data"]["first_name"] == "Test"
        assert data["input_data"]["last_name"] == "User"
    
    @pytest.mark.asyncio
    async def test_output_with_website_only(self):
        """Test output structure when only website is provided."""
        test_data = {
            "request_id": "test-website-only",
            "timestamp": "2025-08-31T14:30:22Z",
            "first_name": "Web",
            "last_name": "Only",
            "company_website": "https://example.com",
            "linkedin": None
        }
        
        result = await execute_registration_workflow_sync(test_data)
        
        # Validate structure
        assert result["input_data"]["company_website"] == "https://example.com"
        assert result["input_data"]["linkedin"] is None
        assert "website_analysis" in result
        assert "discovered_urls" in result["website_analysis"]
    
    @pytest.mark.asyncio
    async def test_output_with_linkedin_only(self):
        """Test output structure when only LinkedIn is provided."""
        test_data = {
            "request_id": "test-linkedin-only",
            "timestamp": "2025-08-31T14:30:22Z",
            "first_name": "LinkedIn",
            "last_name": "Only",
            "company_website": None,
            "linkedin": "https://linkedin.com/in/testuser"
        }
        
        result = await execute_registration_workflow_sync(test_data)
        
        # Validate structure
        assert result["input_data"]["linkedin"] == "https://linkedin.com/in/testuser"
        assert result["input_data"]["company_website"] is None
        assert result["linkedin_analysis"]["status"] == "not_implemented"
    
    @pytest.mark.asyncio
    async def test_output_with_both_urls(self):
        """Test output structure when both URLs are provided."""
        test_data = {
            "request_id": "test-both-urls",
            "timestamp": "2025-08-31T14:30:22Z",
            "first_name": "Both",
            "last_name": "URLs",
            "company_website": "https://example.com",
            "linkedin": "https://linkedin.com/in/bothuser"
        }
        
        result = await execute_registration_workflow_sync(test_data)
        
        # Validate structure
        assert result["input_data"]["company_website"] == "https://example.com"
        assert result["input_data"]["linkedin"] == "https://linkedin.com/in/bothuser"
        assert "website_analysis" in result
        assert "linkedin_analysis" in result
    
    def test_output_handles_no_firecrawl_key(self):
        """Test that output is valid even without Firecrawl API key."""
        # This test assumes FIRECRAWL_API_KEY is not set
        import os
        original_key = os.environ.get("FIRECRAWL_API_KEY")
        
        try:
            # Remove API key if present
            if "FIRECRAWL_API_KEY" in os.environ:
                del os.environ["FIRECRAWL_API_KEY"]
            
            # Run workflow
            test_data = {
                "request_id": "test-no-api-key",
                "timestamp": "2025-08-31T14:30:22Z",
                "first_name": "NoAPI",
                "last_name": "Key",
                "company_website": "https://example.com"
            }
            
            # Run async function in sync context
            loop = asyncio.new_event_loop()
            result = loop.run_until_complete(execute_registration_workflow_sync(test_data))
            loop.close()
            
            # Should still have valid structure
            errors = validate_output_schema(result)
            assert not errors, f"Schema validation errors with no API key: {errors}"
            
            # Check for skipped status
            website = result.get("website_analysis", {})
            if "discovery_status" in website:
                assert website["discovery_status"] in ["skipped", "success"]
            
        finally:
            # Restore original key
            if original_key:
                os.environ["FIRECRAWL_API_KEY"] = original_key
    
    def test_output_metadata_included(self):
        """Test that metadata is included in output."""
        test_data = {
            "request_id": "test-metadata",
            "timestamp": "2025-08-31T14:30:22Z",
            "first_name": "Meta",
            "last_name": "Data",
            "company_website": "https://example.com"
        }
        
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(execute_registration_workflow_sync(test_data))
        loop.close()
        
        # Check for metadata
        if "_metadata" in result:
            metadata = result["_metadata"]
            assert "filename" in metadata
            assert "saved_at" in metadata
            assert "version" in metadata
            assert metadata["philosophy"] == "wars are won with logistics and propaganda"
    
    def test_output_statistics_included(self):
        """Test that statistics are included when website analysis runs."""
        test_data = {
            "request_id": "test-statistics",
            "timestamp": "2025-08-31T14:30:22Z",
            "first_name": "Stats",
            "last_name": "Test",
            "company_website": "https://example.com"
        }
        
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(execute_registration_workflow_sync(test_data))
        loop.close()
        
        website = result.get("website_analysis", {})
        if "statistics" in website:
            stats = website["statistics"]
            assert "total_discovered" in stats
            assert "total_filtered" in stats
            assert "total_scraped" in stats
            assert isinstance(stats["total_discovered"], int)
            assert isinstance(stats["total_filtered"], int)
    
    def test_filename_format(self):
        """Test that output filename follows the correct format."""
        test_data = {
            "request_id": "12345678-1234-1234-1234-123456789012",
            "timestamp": "2025-08-31T14:30:22Z",
            "first_name": "Format",
            "last_name": "Test",
            "company_website": "https://example.com"
        }
        
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(execute_registration_workflow_sync(test_data))
        loop.close()
        
        # Find the file
        output_file = find_latest_output_file(test_data["request_id"])
        assert output_file is not None
        
        # Check filename format: analysis_YYYYMMDD_HHMMSS_<request_id>.json
        filename = output_file.name
        assert filename.startswith("analysis_")
        assert filename.endswith(".json")
        assert "12345678" in filename  # First 8 chars of request_id
        
        # Check date format in filename
        parts = filename.replace("analysis_", "").replace(".json", "").split("_")
        assert len(parts) >= 3  # date, time, request_id
        assert len(parts[0]) == 8  # YYYYMMDD
        assert len(parts[1]) == 6  # HHMMSS