"""
Main Entry Point

AgentCore Runtime wrapper for the AIOps Proactive Workflow.
Manages scaling, invocations, and health checks automatically.
"""

import json
import sys
import threading
import uuid
from pathlib import Path

from bedrock_agentcore import BedrockAgentCoreApp
from bedrock_agentcore.runtime.context import BedrockAgentCoreContext
from dotenv import load_dotenv
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv()

from src.agents import OrchestratorAgent
from src.utils.logging_config import get_logger, setup_logging
from src.workflows import AIOpsSwarm, run_proactive_workflow

setup_logging()
logger = get_logger("main")

# Initialize AgentCore app with CORS middleware
app = BedrockAgentCoreApp(
    middleware=[
        Middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=False,
            allow_methods=["GET", "POST"],
            allow_headers=["*"],
        )
    ]
)


@app.entrypoint
def invoke(payload: dict) -> dict:
    """
    Main entry point for AgentCore invocations.

    Supports three modes:
    - "proactive": Run the full proactive workflow (default)
    - "chat": Interactive chat with session support (A new session ID is created if not provided in payload)
    - "swarm": Run a single task through the Swarm

    Payload Examples:
        {"mode": "proactive"}
        {"mode": "chat", "message": "Why is payment-service failing?"}
        {"mode": "chat", "session_id": "abc-123", "message": "Create a ticket"}
        {"mode": "swarm", "task": "Analyze auth-service errors"}

    Returns:
        Workflow result dictionary.
    """
    logger.info(f"AgentCore invoked: {json.dumps(payload)[:200]}...")

    mode = payload.get("mode", "proactive")

    try:
        if mode == "proactive":
            return handle_proactive(payload)
        elif mode == "chat":
            return handle_chat(payload)
        elif mode == "swarm":
            return handle_swarm(payload)
        else:
            return {
                "success": False,
                "error": f"Unknown mode: {mode}",
                "supported_modes": ["proactive", "chat", "swarm"],
            }

    except Exception as e:
        logger.error(f"Invocation failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "mode": mode,
        }


def handle_proactive(payload: dict) -> dict:
    """Handle proactive workflow mode - starts in background, returns immediately."""

    task_id = app.add_async_task("proactive_workflow")
    logger.info(f"Starting proactive workflow in background (task_id: {task_id})")

    def run_in_background():
        try:
            result = run_proactive_workflow()
            logger.info(f"Workflow completed: {result}")
        except Exception as e:
            logger.error(f"Workflow failed: {e}")
        finally:
            app.complete_async_task(task_id)

    thread = threading.Thread(target=run_in_background, daemon=True)
    thread.start()

    return {
        "success": True,
        "status": "started",
        "task_id": task_id,
        "message": "Proactive workflow started in background",
    }


def handle_chat(payload: dict) -> dict:
    """
    Handle interactive chat mode with session support.

    Uses the OrchestratorAgent for multi-turn conversations.
    When deployed on AgentCore with memory configured, conversation
    history is persisted via the AgentCore Memory service.
    """
    message = payload.get("message", "")
    session_id = payload.get("session_id")
    actor_id = payload.get("actor_id")

    if not message:
        return {"success": False, "error": "Missing 'message' in payload"}

    # Try to get session_id from AgentCore context first (when deployed)
    # AgentCore provides session ID via X-Amzn-Bedrock-AgentCore-Runtime-Session-Id header
    agentcore_session_id = BedrockAgentCoreContext.get_session_id()
    if agentcore_session_id:
        session_id = agentcore_session_id
        logger.info(f"Using AgentCore-provided session ID: {session_id}")

    # Generate session_id if not provided (local development or first interaction)
    is_new_session = False
    if not session_id:
        session_id = str(uuid.uuid4())
        is_new_session = True
        logger.info(f"New chat session created: {session_id}")
    else:
        logger.info(f"Continuing chat session: {session_id}")

    # Use actor_id from payload, or default to session_id for consistency
    # Actor ID identifies the user/entity in AgentCore Memory
    # Using session_id as default ensures messages are found across invocations
    is_new_actor = False
    if not actor_id:
        actor_id = session_id  # Use session_id as actor_id for consistent lookup
        is_new_actor = is_new_session
        logger.info(f"Using session_id as actor_id: {actor_id}")

    # Create orchestrator with session and memory enabled
    # Memory persistence is handled via AgentCore Memory service when deployed
    orchestrator = OrchestratorAgent(
        session_id=session_id,
        enable_memory=True,
        actor_id=actor_id,
    )

    # Invoke the orchestrator with the user message
    logger.info(f"Processing chat message: {message[:100]}...")

    try:
        response = orchestrator.invoke(message)

        # Extract the response text
        response_text = str(response) if response else "No response generated"

        return {
            "success": True,
            "session_id": session_id,
            "actor_id": actor_id,
            "is_new_session": is_new_session,
            "is_new_actor": is_new_actor,
            "response": response_text,
        }

    except Exception as e:
        logger.error(f"Chat invocation failed: {e}")
        return {
            "success": False,
            "session_id": session_id,
            "actor_id": actor_id,
            "error": str(e),
        }


def handle_swarm(payload: dict) -> dict:
    """Handle swarm task mode."""
    task = payload.get("task", "")

    if not task:
        return {"success": False, "error": "Missing 'task' in payload"}

    logger.info(f"Running swarm task: {task[:100]}...")

    swarm = AIOpsSwarm()
    result = swarm.run(task)

    return result.to_dict()


@app.ping
def health() -> dict:
    """Health check endpoint for AgentCore (GET /ping)."""
    return {"status": "healthy", "service": "aiops-proactive-workflow"}


# Start the AgentCore server when executed directly
if __name__ == "__main__":
    logger.info("Starting AgentCore server on port 8080")
    app.run(port=8080)
