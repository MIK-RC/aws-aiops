"""
FastAPI Application

Single API endpoint for the AIOps Orchestrator Agent.
The orchestrator handles all user requests intelligently based on natural language input.
"""

import uuid
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# Load environment variables
load_dotenv()

from ..agents import OrchestratorAgent
from ..utils.logging_config import setup_logging, get_logger
from .schemas import InvokeRequest, InvokeResponse, HealthResponse, ErrorResponse

# Initialize logging
setup_logging()
logger = get_logger("api.app")

# Store active orchestrator sessions
_sessions: dict[str, OrchestratorAgent] = {}


def get_or_create_session(session_id: str | None) -> tuple[OrchestratorAgent, str]:
    """
    Get an existing orchestrator session or create a new one.
    
    Args:
        session_id: Optional session ID. If None, creates a new session.
        
    Returns:
        Tuple of (OrchestratorAgent, session_id)
    """
    if session_id and session_id in _sessions:
        logger.debug(f"Reusing existing session: {session_id}")
        return _sessions[session_id], session_id
    
    # Generate new session ID if not provided
    if not session_id:
        session_id = f"sess-{uuid.uuid4().hex[:8]}"
    
    # Create new orchestrator for this session
    logger.info(f"Creating new session: {session_id}")
    orchestrator = OrchestratorAgent(
        session_id=session_id,
        use_s3_storage=False,  # Use file storage for simplicity
        storage_dir="./sessions",
    )
    
    _sessions[session_id] = orchestrator
    return orchestrator, session_id


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("Starting AIOps Orchestrator API")
    yield
    logger.info("Shutting down AIOps Orchestrator API")
    _sessions.clear()


# Create FastAPI application
app = FastAPI(
    title="AIOps Orchestrator API",
    description="""
## AIOps Multi-Agent Orchestrator

A single intelligent endpoint for all AIOps operations. The orchestrator agent 
understands natural language and routes your requests to the appropriate 
specialist agents (DataDog, Coding, ServiceNow).

### Capabilities

- **Log Analysis**: "Analyze errors in the payment service for the last 24 hours"
- **Issue Investigation**: "What caused the database connection failures yesterday?"
- **Ticket Creation**: "Create a ticket for the authentication issues we found"
- **Daily Reports**: "Run the daily analysis report"

### Session Management

- If you don't provide a `session_id`, a new one will be created and returned
- Use the returned `session_id` in subsequent requests to maintain conversation context
- This allows for follow-up questions and multi-turn conversations
    """,
    version="1.0.0",
    lifespan=lifespan,
    responses={
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post(
    "/invoke",
    response_model=InvokeResponse,
    summary="Invoke the Orchestrator Agent",
    description="""
Send a message to the orchestrator agent and receive an intelligent response.

The orchestrator will:
- Understand your request
- Ask clarifying questions if information is missing
- Execute the appropriate actions using specialist agents
- Return a comprehensive response

**Session Handling:**
- Omit `session_id` to start a new conversation
- Include `session_id` from a previous response to continue that conversation
    """,
    responses={
        200: {
            "description": "Successful response from the orchestrator",
            "content": {
                "application/json": {
                    "examples": {
                        "analysis_request": {
                            "summary": "Log analysis request",
                            "value": {
                                "response": "I analyzed the payment service logs for the last 24 hours and found 3 critical errors...",
                                "session_id": "sess-a1b2c3d4"
                            }
                        },
                        "clarification_needed": {
                            "summary": "Clarification needed",
                            "value": {
                                "response": "I'd be happy to analyze the DataDog logs. Could you please specify the time range?",
                                "session_id": "sess-a1b2c3d4"
                            }
                        }
                    }
                }
            }
        },
        400: {"model": ErrorResponse, "description": "Invalid request"},
    },
)
async def invoke(request: InvokeRequest) -> InvokeResponse:
    """
    Invoke the orchestrator agent with a user message.
    
    The orchestrator intelligently handles all types of requests:
    - Log analysis and investigation
    - Error pattern detection
    - Ticket creation
    - Daily reports
    - General questions about system health
    """
    logger.info(f"Received invoke request: {request.message[:100]}...")
    
    try:
        # Get or create session
        orchestrator, session_id = get_or_create_session(request.session_id)
        
        # Invoke the orchestrator
        response = orchestrator.invoke(request.message)
        
        logger.info(f"Session {session_id}: Response generated successfully")
        
        return InvokeResponse(
            response=response,
            session_id=session_id,
        )
        
    except Exception as e:
        logger.error(f"Error processing request: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Health Check",
    description="Check if the service is running and healthy.",
)
async def health() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        service="aiops-orchestrator",
        version="1.0.0",
    )


@app.get(
    "/",
    include_in_schema=False,
)
async def root():
    """Root endpoint - redirect to docs."""
    return {
        "message": "AIOps Orchestrator API",
        "docs": "/docs",
        "health": "/health",
    }
