"""
FastAPI Application

Simple API for the AIOps Orchestrator Agent.
"""

import uuid

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException

load_dotenv()

from ..agents import OrchestratorAgent
from ..utils.logging_config import setup_logging, get_logger

setup_logging()
logger = get_logger("api")

app = FastAPI(title="AIOps Orchestrator API", version="1.0.0")

# Store sessions in memory
_sessions: dict[str, OrchestratorAgent] = {}


@app.post("/invoke")
async def invoke(request: dict):
    """
    Send a message to the orchestrator agent.

    Request body:
        {
            "message": "Analyze errors in payment service",
            "session_id": "optional-session-id"
        }

    Response:
        {
            "response": "I analyzed the payment service...",
            "session_id": "sess-abc123"
        }
    """
    # Validate message
    message = request.get("message")
    if not message or not isinstance(message, str):
        raise HTTPException(status_code=400, detail="'message' is required")

    # Get or create session
    session_id = request.get("session_id")
    if not session_id:
        session_id = f"sess-{uuid.uuid4().hex[:8]}"

    if session_id not in _sessions:
        logger.info(f"Creating new session: {session_id}")
        _sessions[session_id] = OrchestratorAgent(
            session_id=session_id,
            use_s3_storage=False,
            storage_dir="./sessions",
        )

    # Invoke orchestrator
    try:
        response = _sessions[session_id].invoke(message)
        return {"response": response, "session_id": session_id}
    except Exception as e:
        logger.error(f"Error invoking orchestrator: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


def main():
    """Run the API server."""
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
