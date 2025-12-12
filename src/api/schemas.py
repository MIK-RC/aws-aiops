"""
API Schemas

Pydantic models for request and response validation.
"""

from typing import Optional

from pydantic import BaseModel, Field


class InvokeRequest(BaseModel):
    """Request model for the /invoke endpoint."""
    
    message: str = Field(
        ...,
        description="The user's message or request to the orchestrator agent.",
        min_length=1,
        examples=["Analyze errors in the payment service for the last 24 hours"],
    )
    session_id: Optional[str] = Field(
        default=None,
        description="Optional session ID for conversation continuity. "
                    "If not provided, a new session will be created.",
        examples=["sess-a1b2c3d4"],
    )


class InvokeResponse(BaseModel):
    """Response model for the /invoke endpoint."""
    
    response: str = Field(
        ...,
        description="The orchestrator agent's response.",
    )
    session_id: str = Field(
        ...,
        description="Session ID for this conversation. Use this in subsequent "
                    "requests to maintain conversation continuity.",
    )


class HealthResponse(BaseModel):
    """Response model for the /health endpoint."""
    
    status: str = Field(
        default="healthy",
        description="Health status of the service.",
    )
    service: str = Field(
        default="aiops-orchestrator",
        description="Name of the service.",
    )
    version: str = Field(
        default="1.0.0",
        description="Version of the service.",
    )


class ErrorResponse(BaseModel):
    """Response model for error responses."""
    
    error: str = Field(
        ...,
        description="Error message describing what went wrong.",
    )
    detail: Optional[str] = Field(
        default=None,
        description="Additional error details.",
    )
