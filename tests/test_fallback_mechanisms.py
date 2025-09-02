"""
Test fallback mechanisms when API keys are missing or services are unavailable.
Ensures graceful degradation in all scenarios.
"""

import pytest
from unittest.mock import patch, MagicMock
import httpx

from core.clients.firecrawl import FirecrawlClient
from core.clients.inngest import validate_webhook_signature, trigger_event
from features.website_analysis import discover


class TestFirecrawlFallbacks:
    """Test Firecrawl client fallback mechanisms."""
    
    def test_firecrawl_without_api_key(self):
        """Test Firecrawl client behavior without API key."""
        client = FirecrawlClient(api_key=None)
        
        assert not client.has_key
        assert client.api_key is None
    
    @pytest.mark.asyncio
    async def test_crawl_without_api_key(self):
        """Test crawling without API key returns fallback response."""
        client = FirecrawlClient(api_key=None)
        
        result = await client.crawl("https://example.com")
        
        assert result["status"] == "skipped"
        assert result["reason"] == "no_api_key"
        assert result["urls"] == ["https://example.com"]
    
    @pytest.mark.asyncio
    async def test_scrape_without_api_key(self):
        """Test scraping without API key returns mock response."""
        client = FirecrawlClient(api_key=None)
        
        result = await client.scrape("https://example.com")
        
        assert result["status"] == "skipped"
        assert result["reason"] == "no_api_key"
        assert "would be scraped here" in result["content"]
    
    @pytest.mark.asyncio
    async def test_rate_limiting_backoff(self):
        """Test exponential backoff on rate limiting."""
        client = FirecrawlClient(api_key="test-key")
        
        # Mock the _calculate_backoff_delay method
        with patch.object(client, '_calculate_backoff_delay') as mock_backoff:
            mock_backoff.return_value = 0.1  # Short delay for testing
            
            # Mock HTTP client to return 429
            with patch.object(client.client, 'post') as mock_post:
                # First call returns 429, second call succeeds
                mock_response_429 = MagicMock()
                mock_response_429.status_code = 429
                mock_response_429.is_success = False
                
                mock_response_200 = MagicMock()
                mock_response_200.status_code = 200
                mock_response_200.is_success = True
                mock_response_200.json.return_value = {"data": [{"url": "https://example.com"}]}
                
                mock_post.side_effect = [mock_response_429, mock_response_200]
                
                # Should retry and succeed
                result = await client.crawl("https://example.com")
                
                assert result["status"] == "success"
                assert mock_post.call_count == 2  # Original call + 1 retry
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_functionality(self):
        """Test circuit breaker opens after repeated failures."""
        client = FirecrawlClient(api_key="test-key")
        
        # Simulate repeated failures to trigger circuit breaker
        for _ in range(5):
            client._record_failure()
        
        assert client.circuit_open
        
        # Circuit breaker should prevent further requests
        with patch.object(client, '_is_circuit_open') as mock_circuit:
            mock_circuit.return_value = True
            
            result = await client.crawl("https://example.com")
            
            assert result["status"] == "circuit_open"
            assert result["reason"] == "circuit_breaker_open"
    
    @pytest.mark.asyncio
    async def test_fallback_url_discovery(self):
        """Test fallback URL discovery when Firecrawl is unavailable."""
        result = await discover.discover_urls_fallback("https://example.com")
        
        assert result["status"] == "success"
        assert result["method"] == "fallback_patterns"
        assert len(result["urls"]) > 10  # Should generate many common URLs
        
        # Verify common patterns are included
        urls = result["urls"]
        assert "https://example.com/about" in urls
        assert "https://example.com/team" in urls
        assert "https://example.com/services" in urls
    
    def test_retryable_error_classification(self):
        """Test proper classification of retryable vs non-retryable errors."""
        client = FirecrawlClient(api_key="test-key")
        
        # Rate limits should be retryable
        assert client._is_retryable_error(429) is True
        
        # Server errors should be retryable
        assert client._is_retryable_error(500) is True
        assert client._is_retryable_error(503) is True
        
        # Client errors should not be retryable
        assert client._is_retryable_error(400) is False
        assert client._is_retryable_error(404) is False
        
        # Timeout exceptions should be retryable
        assert client._is_retryable_error(0, httpx.TimeoutException("timeout")) is True
        
        # Connection errors should be retryable
        assert client._is_retryable_error(0, httpx.ConnectError("connection failed")) is True


class TestInngestFallbacks:
    """Test Inngest client fallback mechanisms."""
    
    def test_webhook_signature_validation_without_key(self):
        """Test webhook signature validation in development mode."""
        # Without signing key, should allow all requests
        result = validate_webhook_signature(
            payload=b'{"test": "data"}',
            signature="s=invalid_signature",
            signing_key=None
        )
        
        assert result is True
    
    def test_webhook_signature_validation_with_key(self):
        """Test webhook signature validation with signing key."""
        import hmac
        import hashlib
        
        payload = b'{"test": "data"}'
        signing_key = "test-secret-key"
        
        # Generate valid signature
        expected_signature = hmac.new(
            signing_key.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        # Valid signature should pass
        result = validate_webhook_signature(
            payload=payload,
            signature=f"s={expected_signature}",
            signing_key=signing_key
        )
        
        assert result is True
        
        # Invalid signature should fail
        result = validate_webhook_signature(
            payload=payload,
            signature="s=invalid_signature",
            signing_key=signing_key
        )
        
        assert result is False
    
    def test_webhook_signature_validation_malformed_signature(self):
        """Test webhook signature validation with malformed signature."""
        result = validate_webhook_signature(
            payload=b'{"test": "data"}',
            signature="invalid_format",  # Missing "s=" prefix
            signing_key="test-key"
        )
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_inngest_event_trigger_fallback(self):
        """Test Inngest event triggering with error handling."""
        with patch('core.clients.inngest.inngest_client') as mock_client:
            # Simulate Inngest client failure
            mock_client.send.side_effect = Exception("Inngest unavailable")
            
            result = await trigger_event(
                "test.event",
                {"test": "data"}
            )
            
            # Should return False but not raise exception
            assert result is False
    
    @pytest.mark.asyncio
    async def test_inngest_correlation_id_tracking(self):
        """Test that correlation IDs are properly tracked."""
        with patch('core.clients.inngest.inngest_client') as mock_client:
            mock_client.send.return_value = None
            
            # Test with explicit event ID
            result = await trigger_event(
                "test.event",
                {"test": "data"},
                event_id="custom-id"
            )
            
            # Should use the custom ID
            call_args = mock_client.send.call_args[0][0]  # First argument (Event object)
            assert call_args.id == "custom-id"
            assert result is True


class TestGracefulDegradation:
    """Test overall system graceful degradation."""
    
    @pytest.mark.asyncio
    async def test_website_analysis_with_all_failures(self):
        """Test website analysis when all external services fail."""
        from features.workflows.register_workflow import analyze_website
        
        with patch('features.website_analysis.discover.discover_urls') as mock_discover:
            with patch('features.website_analysis.filter.filter_urls') as mock_filter:
                with patch('features.website_analysis.scrape.scrape_urls') as mock_scrape:
                    # All services fail
                    mock_discover.return_value = {
                        "status": "error",
                        "reason": "service_unavailable",
                        "urls": ["https://example.com"]  # Fallback
                    }
                    mock_filter.return_value = {
                        "urls": ["https://example.com"],
                        "reasons": {}
                    }
                    mock_scrape.return_value = {
                        "results": [{
                            "url": "https://example.com",
                            "status": "error",
                            "reason": "service_unavailable",
                            "content": ""
                        }]
                    }
                    
                    result = await analyze_website("https://example.com")
                    
                    # Should still return structured data
                    assert "discovered_urls" in result
                    assert "filtered_urls" in result
                    assert "scraped_content" in result
                    assert "statistics" in result
                    
                    # Statistics should reflect the failures
                    stats = result["statistics"]
                    assert stats["total_discovered"] >= 1  # At least the fallback URL
                    assert stats["scrape_failures"] >= 0
    
    @pytest.mark.asyncio
    async def test_complete_workflow_degradation(self):
        """Test complete workflow with various service failures."""
        from features.workflows.register_workflow import execute_registration_workflow_sync
        
        sample_data = {
            "request_id": "test-fallback",
            "timestamp": "2025-09-02T00:00:00Z",
            "first_name": "Test",
            "last_name": "Fallback",
            "company_website": "https://example.com",
            "linkedin": "https://linkedin.com/in/test"
        }
        
        # Mock all external dependencies to simulate failures
        with patch('features.website_analysis.discover.discover_urls') as mock_discover:
            with patch('features.website_analysis.filter.filter_urls') as mock_filter:
                with patch('features.website_analysis.scrape.scrape_urls') as mock_scrape:
                    with patch('core.utils.write_json') as mock_write:
                        # Configure fallback responses
                        mock_discover.return_value = {
                            "status": "error",
                            "reason": "all_services_down",
                            "urls": ["https://example.com"]
                        }
                        mock_filter.return_value = {
                            "urls": ["https://example.com"],
                            "reasons": {}
                        }
                        mock_scrape.return_value = {
                            "results": [{
                                "url": "https://example.com",
                                "status": "error",
                                "content": ""
                            }]
                        }
                        mock_write.return_value = True  # File write succeeds
                        
                        # Workflow should complete without throwing exceptions
                        result = await execute_registration_workflow_sync(sample_data)
                        
                        # Should return well-formed result
                        assert result["request_id"] == "test-fallback"
                        assert result["linkedin_analysis"]["status"] == "not_implemented"
                        assert "website_analysis" in result
                        
                        # Should attempt to save results
                        assert mock_write.called
    
    def test_invalid_url_handling(self):
        """Test handling of invalid URLs throughout the system."""
        from core.utils import safe_url
        
        # Test various invalid URL formats
        assert safe_url("") is None
        assert safe_url("   ") is None
        assert safe_url("not-a-url") is not None  # Should add https://
        assert safe_url("javascript:alert('xss')") is None  # Should be rejected
        
        # Test URL normalization
        normalized = safe_url("example.com")
        assert normalized == "https://example.com"
        
        normalized = safe_url("http://example.com")
        assert normalized == "http://example.com"  # Should preserve existing scheme
    
    def test_configuration_fallbacks(self):
        """Test that system works with minimal configuration."""
        from core.config import Settings
        from pathlib import Path
        
        # Test with minimal environment
        settings = Settings(
            _env_file=None,  # Don't load from file
            FIRECRAWL_API_KEY=None,
            INNGEST_EVENT_KEY=None
        )
        
        # Should have sensible defaults
        assert settings.OUTPUT_DIR == Path("outputs")
        assert settings.FIRECRAWL_MAX_URLS == 50
        assert settings.OUTPUT_INCLUDE_PERSON_NAME is True
        assert settings.BI_URL_LIMIT == 7
        
        # Should handle missing optional config
        assert settings.OUTPUT_RETENTION_DAYS is None
        assert not settings.OUTPUT_CLEANUP_ON_STARTUP