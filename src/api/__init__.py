"""
API Module

FastAPI application for the AIOps Multi-Agent System.
Provides a single endpoint for interacting with the Orchestrator agent.
"""

from .app import app

__all__ = ["app"]
