"""
Test health check endpoints.
Verifies /health and /health/detailed return 200 and useful info.
"""

import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_basic_health_endpoint():
    """Test that /health returns 200 and basic status."""
    response = client.get("/health")
    
    # Check status code
    assert response.status_code == 200
    
    # Check response structure
    data = response.json()
    assert "status" in data
    assert "timestamp" in data
    assert "service" in data
    
    # Check values
    assert data["status"] == "healthy"
    assert data["service"] == "astral-assessment"
    
    # Timestamp should be ISO format
    assert "T" in data["timestamp"]  # Basic ISO format check


def test_detailed_health_endpoint():
    """Test that /health/detailed returns 200 and comprehensive info."""
    response = client.get("/health/detailed")
    
    # Check status code
    assert response.status_code == 200
    
    # Check response structure
    data = response.json()
    
    # Required top-level fields
    required_fields = [
        "status", "timestamp", "service", "version",
        "environment", "system", "process", "application",
        "integrations", "philosophy"
    ]
    
    for field in required_fields:
        assert field in data, f"Missing required field: {field}"
    
    # Check status
    assert data["status"] == "healthy"
    assert data["service"] == "astral-assessment"
    assert data["version"] == "1.0.0"
    
    # Check philosophy (astral requirement)
    assert data["philosophy"] == "wars are won with logistics and propaganda"
    
    # Check system info
    assert "platform" in data["system"]
    assert "python_version" in data["system"]
    assert "cpu_count" in data["system"]
    
    # Check process info
    assert "pid" in data["process"]
    assert "memory_usage_mb" in data["process"]
    assert "cpu_percent" in data["process"]
    assert "threads" in data["process"]
    assert "uptime_seconds" in data["process"]
    
    # Check application info
    assert "output_files_count" in data["application"]
    assert "output_directory" in data["application"]
    assert "log_level" in data["application"]
    
    # Check integrations
    assert "inngest" in data["integrations"]
    assert "firecrawl" in data["integrations"]
    
    # Check Inngest integration details
    inngest = data["integrations"]["inngest"]
    assert "configured" in inngest
    assert "app_id" in inngest
    assert "event_key" in inngest
    
    # Check Firecrawl integration details
    firecrawl = data["integrations"]["firecrawl"]
    assert "configured" in firecrawl
    assert "api_url" in firecrawl
    assert "has_key" in firecrawl


def test_health_endpoints_are_fast():
    """Test that health endpoints respond quickly."""
    import time
    
    # Basic health should be very fast
    start = time.time()
    response = client.get("/health")
    duration = time.time() - start
    
    assert response.status_code == 200
    assert duration < 0.5, f"Basic health check took {duration:.3f}s, should be < 0.5s"
    
    # Detailed health can be a bit slower but still fast
    start = time.time()
    response = client.get("/health/detailed")
    duration = time.time() - start
    
    assert response.status_code == 200
    assert duration < 1.0, f"Detailed health check took {duration:.3f}s, should be < 1.0s"


def test_health_endpoint_headers():
    """Test that health endpoints include proper headers."""
    response = client.get("/health")
    
    # Should have timing headers from middleware
    assert "X-Request-ID" in response.headers
    assert "X-Process-Time" in response.headers
    
    # Process time should be a valid float
    process_time = float(response.headers["X-Process-Time"])
    assert process_time > 0
    assert process_time < 1.0  # Should be fast


def test_detailed_health_memory_tracking():
    """Test that memory usage is tracked properly."""
    response = client.get("/health/detailed")
    data = response.json()
    
    memory_mb = data["process"]["memory_usage_mb"]
    
    # Memory should be a reasonable value (more than 10MB, less than 1000MB for a FastAPI app)
    assert memory_mb > 10, f"Memory usage seems too low: {memory_mb}MB"
    assert memory_mb < 1000, f"Memory usage seems too high: {memory_mb}MB"


def test_health_output_directory_exists():
    """Test that the output directory is properly reported."""
    response = client.get("/health/detailed")
    data = response.json()
    
    output_dir = data["application"]["output_directory"]
    assert output_dir == "outputs" or output_dir.endswith("/outputs")
    
    # Check file count is a valid number
    file_count = data["application"]["output_files_count"]
    assert isinstance(file_count, int)
    assert file_count >= 0


def test_health_integration_status():
    """Test that integration status is properly reported."""
    response = client.get("/health/detailed")
    data = response.json()
    
    # Inngest should always have an app_id
    inngest = data["integrations"]["inngest"]
    assert inngest["app_id"] in ["astral-assessment", "not_configured"]
    
    # Firecrawl should have a valid URL
    firecrawl = data["integrations"]["firecrawl"]
    assert firecrawl["api_url"] == "https://api.firecrawl.dev/v2"
    
    # Check boolean flags
    assert isinstance(inngest["configured"], bool)
    assert isinstance(firecrawl["configured"], bool)
    assert isinstance(firecrawl["has_key"], bool)