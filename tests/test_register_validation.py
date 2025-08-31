"""
Test /register endpoint validation.
Verifies that names are required and at least one of company_website or linkedin must be provided.
"""

import pytest
from fastapi.testclient import TestClient
from main import app
import json

client = TestClient(app)


class TestRegisterValidation:
    """Test validation rules for the /register endpoint."""
    
    def test_valid_request_with_both_urls(self):
        """Test valid request with both company_website and linkedin."""
        payload = {
            "first_name": "Jane",
            "last_name": "Smith",
            "company_website": "https://example.com",
            "linkedin": "https://linkedin.com/in/janesmith"
        }
        
        response = client.post("/register", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "accepted"
        assert "request_id" in data
        assert "Jane Smith" in data["message"]
    
    def test_valid_request_with_only_website(self):
        """Test valid request with only company_website."""
        payload = {
            "first_name": "John",
            "last_name": "Doe",
            "company_website": "https://acme.com"
        }
        
        response = client.post("/register", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "accepted"
        assert "request_id" in data
    
    def test_valid_request_with_only_linkedin(self):
        """Test valid request with only linkedin."""
        payload = {
            "first_name": "Alice",
            "last_name": "Johnson",
            "linkedin": "https://linkedin.com/in/alicej"
        }
        
        response = client.post("/register", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "accepted"
        assert "request_id" in data
    
    def test_invalid_missing_both_urls(self):
        """Test that request fails when both website and linkedin are missing."""
        payload = {
            "first_name": "Bob",
            "last_name": "Wilson"
        }
        
        response = client.post("/register", json=payload)
        
        assert response.status_code == 422  # Validation error
        data = response.json()
        assert "detail" in data
        # Check that error mentions the requirement
        error_msg = str(data["detail"]).lower()
        assert "company_website" in error_msg or "linkedin" in error_msg
    
    def test_invalid_missing_first_name(self):
        """Test that first_name is required."""
        payload = {
            "last_name": "Smith",
            "company_website": "https://example.com"
        }
        
        response = client.post("/register", json=payload)
        
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        # Pydantic will mention the missing field
        assert any("first_name" in str(error).lower() for error in data["detail"])
    
    def test_invalid_missing_last_name(self):
        """Test that last_name is required."""
        payload = {
            "first_name": "Jane",
            "company_website": "https://example.com"
        }
        
        response = client.post("/register", json=payload)
        
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        assert any("last_name" in str(error).lower() for error in data["detail"])
    
    def test_invalid_empty_first_name(self):
        """Test that empty first_name is rejected."""
        payload = {
            "first_name": "",
            "last_name": "Smith",
            "company_website": "https://example.com"
        }
        
        response = client.post("/register", json=payload)
        
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
    
    def test_invalid_empty_last_name(self):
        """Test that empty last_name is rejected."""
        payload = {
            "first_name": "Jane",
            "last_name": "   ",  # Just whitespace
            "company_website": "https://example.com"
        }
        
        response = client.post("/register", json=payload)
        
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
    
    def test_invalid_empty_urls_count_as_missing(self):
        """Test that empty URL strings count as missing."""
        payload = {
            "first_name": "Jane",
            "last_name": "Smith",
            "company_website": "",
            "linkedin": ""
        }
        
        response = client.post("/register", json=payload)
        
        assert response.status_code == 422
        data = response.json()
        # Should fail the "at least one" validation
        error_msg = str(data["detail"]).lower()
        assert "at least one" in error_msg or "company_website" in error_msg or "linkedin" in error_msg
    
    def test_urls_without_protocol_accepted(self):
        """Test that URLs without protocol are accepted (will be normalized)."""
        payload = {
            "first_name": "Jane",
            "last_name": "Smith",
            "company_website": "example.com",  # No https://
            "linkedin": "linkedin.com/in/janesmith"  # No https://
        }
        
        response = client.post("/register", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "accepted"
    
    def test_whitespace_trimmed_from_names(self):
        """Test that whitespace is trimmed from names."""
        payload = {
            "first_name": "  Jane  ",
            "last_name": "  Smith  ",
            "company_website": "https://example.com"
        }
        
        response = client.post("/register", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert "Jane Smith" in data["message"]  # Should be trimmed
    
    def test_very_long_names_rejected(self):
        """Test that very long names are rejected."""
        payload = {
            "first_name": "A" * 101,  # Max is 100
            "last_name": "Smith",
            "company_website": "https://example.com"
        }
        
        response = client.post("/register", json=payload)
        
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
    
    def test_very_long_urls_rejected(self):
        """Test that very long URLs are rejected."""
        payload = {
            "first_name": "Jane",
            "last_name": "Smith",
            "company_website": "https://example.com/" + "a" * 500  # Max is 500 total
        }
        
        response = client.post("/register", json=payload)
        
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
    
    def test_null_values_handled(self):
        """Test that null values for optional fields are handled."""
        payload = {
            "first_name": "Jane",
            "last_name": "Smith",
            "company_website": "https://example.com",
            "linkedin": None
        }
        
        response = client.post("/register", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "accepted"
    
    def test_response_includes_request_id(self):
        """Test that successful response includes request_id."""
        payload = {
            "first_name": "Jane",
            "last_name": "Smith",
            "company_website": "https://example.com"
        }
        
        response = client.post("/register", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert "request_id" in data
        assert len(data["request_id"]) == 36  # UUID format
        assert "-" in data["request_id"]  # UUID has dashes
    
    def test_response_includes_timestamp(self):
        """Test that successful response includes ISO timestamp."""
        payload = {
            "first_name": "Jane",
            "last_name": "Smith",
            "company_website": "https://example.com"
        }
        
        response = client.post("/register", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert "timestamp" in data
        assert "T" in data["timestamp"]  # ISO format
        assert "Z" in data["timestamp"] or "+" in data["timestamp"]  # Timezone info