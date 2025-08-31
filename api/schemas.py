"""
Pydantic v2 models for request/response validation
Following astral-os guidelines for using Pydantic v2
"""

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, List, Dict, Any
from datetime import datetime


class RegisterRequest(BaseModel):
    """
    Request model for /register endpoint.
    Requires first_name, last_name, and at least one of company_website or linkedin.
    """
    first_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="First name of the person to research"
    )
    last_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Last name of the person to research"
    )
    company_website: Optional[str] = Field(
        None,
        max_length=500,
        description="Company website URL for analysis"
    )
    linkedin: Optional[str] = Field(
        None,
        max_length=500,
        description="LinkedIn profile URL"
    )
    
    @field_validator('first_name', 'last_name')
    @classmethod
    def validate_names(cls, v: str) -> str:
        """Strip whitespace and ensure non-empty"""
        v = v.strip()
        if not v:
            raise ValueError("Name cannot be empty or just whitespace")
        return v
    
    @field_validator('company_website', 'linkedin')
    @classmethod
    def validate_urls(cls, v: Optional[str]) -> Optional[str]:
        """Clean up URLs - basic validation"""
        if v is None:
            return None
        v = v.strip()
        if not v:
            return None
        # Don't do heavy URL validation here - let Firecrawl handle it
        return v
    
    @model_validator(mode='after')
    def validate_at_least_one_source(self) -> 'RegisterRequest':
        """
        Validation requirement: At least one of company_website or linkedin must be provided.
        Fail early if neither is passed.
        """
        if not self.company_website and not self.linkedin:
            raise ValueError(
                "At least one of 'company_website' or 'linkedin' must be provided"
            )
        return self
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "first_name": "Jane",
                    "last_name": "Smith",
                    "company_website": "https://example.com",
                    "linkedin": "https://linkedin.com/in/janesmith"
                },
                {
                    "first_name": "John",
                    "last_name": "Doe",
                    "company_website": "https://acme.com"
                }
            ]
        }
    }


class RegisterAccepted(BaseModel):
    """
    Response model for successful registration acceptance
    """
    status: str = Field(
        default="accepted",
        description="Status of the registration request"
    )
    request_id: str = Field(
        ...,
        description="Unique identifier for tracking this request"
    )
    message: str = Field(
        ...,
        description="Human-readable message about the registration"
    )
    timestamp: str = Field(
        ...,
        description="ISO timestamp of when the request was accepted"
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "accepted",
                "request_id": "550e8400-e29b-41d4-a716-446655440000",
                "message": "Registration accepted for Jane Smith. Processing in background.",
                "timestamp": "2025-08-31T14:30:22Z"
            }
        }
    }


class ErrorResponse(BaseModel):
    """
    Standard error response model
    """
    error: str = Field(
        ...,
        description="Error type or code"
    )
    message: str = Field(
        ...,
        description="Human-readable error message"
    )
    detail: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional error details if available"
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat(),
        description="When the error occurred"
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "error": "validation_error",
                "message": "At least one of 'company_website' or 'linkedin' must be provided",
                "detail": {
                    "fields": ["company_website", "linkedin"]
                },
                "timestamp": "2025-08-31T14:30:22Z"
            }
        }
    }


class HealthStatus(BaseModel):
    """
    Basic health check response
    """
    status: str
    timestamp: str
    service: str


class DetailedHealthStatus(BaseModel):
    """
    Detailed health check response with system information
    """
    status: str
    timestamp: str
    service: str
    version: str
    environment: str
    system: Dict[str, Any]
    process: Dict[str, Any]
    application: Dict[str, Any]
    integrations: Dict[str, Any]
    philosophy: str = "wars are won with logistics and propaganda"