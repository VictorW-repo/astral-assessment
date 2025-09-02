"""
Integration tests for the complete registration workflow.
Tests the full end-to-end pipeline including enhanced features.
"""

import pytest
import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

from features.workflows.register_workflow import (
    execute_registration_workflow_sync,
    analyze_website,
    save_workflow_results
)
from core.config import settings
from core.utils import generate_output_filename, sanitize_name_for_filename


class TestWorkflowIntegration:
    """Test the complete registration workflow integration."""
    
    @pytest.fixture
    def sample_registration_data(self):
        """Sample registration data for testing."""
        return {
            "request_id": "test-123",
            "timestamp": "2025-09-02T00:00:00Z",
            "first_name": "Test",
            "last_name": "User",
            "company_website": "https://example.com",
            "linkedin": "https://linkedin.com/in/testuser"
        }
    
    @pytest.fixture
    def mock_website_analysis_result(self):
        """Mock website analysis result."""
        return {
            "discovered_urls": ["https://example.com", "https://example.com/about"],
            "filtered_urls": ["https://example.com"],
            "scraped_content": [{
                "url": "https://example.com",
                "content": "# Example Company\nWe are a test company."
            }],
            "statistics": {
                "total_discovered": 2,
                "total_filtered": 1,
                "total_scraped": 1,
                "scrape_failures": 0
            }
        }
    
    @pytest.mark.asyncio
    async def test_complete_workflow_with_website_only(
        self, 
        sample_registration_data, 
        mock_website_analysis_result,
        tmp_path
    ):
        """Test complete workflow with website only."""
        # Remove LinkedIn from test data
        sample_registration_data.pop("linkedin")
        
        # Mock the output directory
        with patch.object(settings, 'OUTPUT_DIR', tmp_path):
            with patch('features.website_analysis.discover.discover_urls') as mock_discover:
                with patch('features.website_analysis.filter.filter_urls') as mock_filter:
                    with patch('features.website_analysis.scrape.scrape_urls') as mock_scrape:
                        # Configure mocks
                        mock_discover.return_value = {
                            "status": "success",
                            "urls": ["https://example.com", "https://example.com/about"]
                        }
                        mock_filter.return_value = {
                            "urls": ["https://example.com"],
                            "reasons": {"https://example.com": "homepage"}
                        }
                        mock_scrape.return_value = {
                            "results": [{
                                "url": "https://example.com",
                                "status": "success",
                                "content": "# Example Company\nWe are a test company."
                            }]
                        }
                        
                        # Execute workflow
                        result = await execute_registration_workflow_sync(sample_registration_data)
                        
                        # Verify result structure
                        assert result["request_id"] == "test-123"
                        assert result["input_data"]["first_name"] == "Test"
                        assert result["input_data"]["last_name"] == "User"
                        assert result["linkedin_analysis"]["status"] == "not_implemented"
                        
                        # Verify website analysis
                        website_analysis = result["website_analysis"]
                        assert len(website_analysis["discovered_urls"]) == 2
                        assert len(website_analysis["filtered_urls"]) == 1
                        assert len(website_analysis["scraped_content"]) == 1
                        assert website_analysis["statistics"]["total_scraped"] == 1
                        
                        # Verify output file was created
                        output_files = list(tmp_path.glob("analysis_*.json"))
                        assert len(output_files) == 1
                        
                        # Verify enhanced filename format
                        output_file = output_files[0]
                        assert "TestU_" in output_file.name  # Should include person name
                        
                        # Verify file content
                        with open(output_file) as f:
                            saved_data = json.load(f)
                        
                        assert saved_data["_metadata"]["person_name"] == "Test User"
                        assert saved_data["_metadata"]["version"] == "1.1.0"
                        assert "resources" in saved_data["_metadata"]
    
    @pytest.mark.asyncio
    async def test_complete_workflow_with_linkedin_only(self, sample_registration_data, tmp_path):
        """Test complete workflow with LinkedIn only."""
        # Remove website from test data
        sample_registration_data.pop("company_website")
        
        # Mock the output directory
        with patch.object(settings, 'OUTPUT_DIR', tmp_path):
            # Execute workflow
            result = await execute_registration_workflow_sync(sample_registration_data)
            
            # Verify result structure
            assert result["request_id"] == "test-123"
            assert result["linkedin_analysis"]["status"] == "not_implemented"
            assert result["linkedin_analysis"]["url"] == "https://linkedin.com/in/testuser"
            
            # Website analysis should be empty
            website_analysis = result["website_analysis"]
            assert len(website_analysis["discovered_urls"]) == 0
            assert len(website_analysis["filtered_urls"]) == 0
            assert len(website_analysis["scraped_content"]) == 0
            
            # Verify output file was created
            output_files = list(tmp_path.glob("analysis_*.json"))
            assert len(output_files) == 1
    
    @pytest.mark.asyncio
    async def test_workflow_error_handling(self, sample_registration_data, tmp_path):
        """Test workflow error handling and partial results saving."""
        with patch.object(settings, 'OUTPUT_DIR', tmp_path):
            with patch('features.website_analysis.discover.discover_urls') as mock_discover:
                # Configure mock to raise an exception
                mock_discover.side_effect = Exception("Discovery failed")
                
                # Execute workflow
                result = await execute_registration_workflow_sync(sample_registration_data)
                
                # Should still save partial results
                assert result["request_id"] == "test-123"
                assert "error" in result["website_analysis"]
                
                # Verify output file was created even with errors
                output_files = list(tmp_path.glob("analysis_*.json"))
                assert len(output_files) == 1
    
    def test_enhanced_filename_generation(self):
        """Test enhanced filename generation with person names."""
        # Test with full name
        filename = generate_output_filename(
            "test-123",
            "Jane",
            "Smith"
        )
        assert "JaneS_" in filename
        assert filename.startswith("analysis_")
        assert filename.endswith(".json")
        
        # Test with first name only
        filename = generate_output_filename(
            "test-123",
            "John",
            None
        )
        assert "John_" in filename
        
        # Test without names
        filename = generate_output_filename(
            "test-123",
            None,
            None
        )
        assert "Jane" not in filename
        assert "John" not in filename
    
    def test_name_sanitization(self):
        """Test name sanitization for filenames."""
        # Test special characters
        assert sanitize_name_for_filename("Jean-Claude") == "JeanClaude"
        
        # Test unicode characters
        assert sanitize_name_for_filename("José") == "Jos"
        
        # Test spaces
        assert sanitize_name_for_filename("Mary Jane") == "MaryJane"
        
        # Test length limiting
        assert len(sanitize_name_for_filename("VeryLongFirstName", 5)) == 5
        
        # Test empty input
        assert sanitize_name_for_filename("") == ""
        assert sanitize_name_for_filename(None) == ""
    
    @pytest.mark.asyncio
    async def test_detailed_logging_configuration(self, sample_registration_data, tmp_path):
        """Test that detailed logging can be enabled/disabled."""
        # Test with detailed logging enabled
        with patch.object(settings, 'OUTPUT_DIR', tmp_path):
            with patch.object(settings, 'OUTPUT_DETAILED_LOGGING', True):
                with patch('features.website_analysis.discover.discover_urls') as mock_discover:
                    with patch('features.website_analysis.filter.filter_urls') as mock_filter:
                        with patch('features.website_analysis.scrape.scrape_urls') as mock_scrape:
                            # Configure mocks
                            mock_discover.return_value = {"status": "success", "urls": ["https://example.com"]}
                            mock_filter.return_value = {"urls": ["https://example.com"], "reasons": {}}
                            mock_scrape.return_value = {"results": [{"url": "https://example.com", "status": "success", "content": "test"}]}
                            
                            result = await execute_registration_workflow_sync(sample_registration_data)
                            
                            # Verify processing log exists
                            assert result.get("_processing_log") is not None
                            
                            # Verify output file contains processing metadata
                            output_files = list(tmp_path.glob("analysis_*.json"))
                            with open(output_files[0]) as f:
                                saved_data = json.load(f)
                            
                            assert "processing" in saved_data["_metadata"]
                            assert "steps" in saved_data["_metadata"]["processing"]
        
        # Test with detailed logging disabled
        with patch.object(settings, 'OUTPUT_DIR', tmp_path):
            with patch.object(settings, 'OUTPUT_DETAILED_LOGGING', False):
                result = await execute_registration_workflow_sync(sample_registration_data)
                
                # Processing log should be None
                assert result.get("_processing_log") is None
    
    @pytest.mark.asyncio
    async def test_processing_statistics_calculation(self, tmp_path):
        """Test processing statistics calculation."""
        from core.utils import calculate_processing_stats, create_processing_log_entry
        
        # Create sample processing log
        processing_log = [
            create_processing_log_entry("url_discovery", 1500, "success", urls_found=10),
            create_processing_log_entry("url_filtering", 200, "success", input_urls=10, output_urls=3),
            create_processing_log_entry("content_scraping", 3000, "success", urls_scraped=3, successful_scrapes=2)
        ]
        
        stats = calculate_processing_stats(processing_log)
        
        assert stats["total_duration_ms"] == 4700
        assert stats["total_duration_seconds"] == 4.7
        assert stats["total_steps"] == 3
        assert stats["status_counts"]["success"] == 3
        assert stats["success_rate"] == 100.0
    
    @pytest.mark.asyncio 
    async def test_resource_usage_tracking(self, sample_registration_data, tmp_path):
        """Test that resource usage is properly tracked in metadata."""
        with patch.object(settings, 'OUTPUT_DIR', tmp_path):
            with patch('features.website_analysis.discover.discover_urls') as mock_discover:
                with patch('features.website_analysis.filter.filter_urls') as mock_filter:
                    with patch('features.website_analysis.scrape.scrape_urls') as mock_scrape:
                        # Configure mocks with specific content sizes
                        test_content = "A" * 1000  # 1000 bytes
                        mock_discover.return_value = {"status": "success", "urls": ["https://example.com"]}
                        mock_filter.return_value = {"urls": ["https://example.com"], "reasons": {}}
                        mock_scrape.return_value = {
                            "results": [{
                                "url": "https://example.com",
                                "status": "success",
                                "content": test_content
                            }]
                        }
                        
                        result = await execute_registration_workflow_sync(sample_registration_data)
                        
                        # Verify resource tracking in output file
                        output_files = list(tmp_path.glob("analysis_*.json"))
                        with open(output_files[0]) as f:
                            saved_data = json.load(f)
                        
                        resources = saved_data["_metadata"]["resources"]
                        assert resources["content_bytes_scraped"] == 1000
                        assert resources["urls_discovered"] == 1
                        assert resources["urls_filtered"] == 1
                        assert resources["urls_scraped"] == 1
                        assert resources["scrape_success_rate"] == 100.0


class TestFallbackMechanisms:
    """Test fallback mechanisms when APIs are unavailable."""
    
    @pytest.mark.asyncio
    async def test_firecrawl_circuit_breaker_fallback(self, tmp_path):
        """Test fallback when Firecrawl circuit breaker is open."""
        from core.clients.firecrawl import FirecrawlClient
        
        # Create client and simulate circuit breaker open
        client = FirecrawlClient(api_key="test-key")
        client.circuit_open = True
        client.failure_count = 10
        
        # Test crawl with circuit breaker open
        result = await client.crawl("https://example.com")
        
        assert result["status"] == "circuit_open"
        assert result["reason"] == "circuit_breaker_open"
        assert len(result["urls"]) == 1  # Should return input URL as fallback
    
    @pytest.mark.asyncio
    async def test_inngest_signature_validation_fallback(self):
        """Test Inngest signature validation with missing key."""
        from core.clients.inngest import validate_webhook_signature
        
        # Test without signing key (development mode)
        result = validate_webhook_signature(
            payload=b'{"test": "data"}',
            signature="s=invalid",
            signing_key=None
        )
        assert result is True  # Should pass in development mode
        
        # Test with signing key but no signature
        result = validate_webhook_signature(
            payload=b'{"test": "data"}',
            signature=None,
            signing_key="test-key"
        )
        assert result is False  # Should fail without signature