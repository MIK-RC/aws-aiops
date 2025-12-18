"""
Main Entry Point

AgentCore Runtime wrapper for the AIOps Proactive Workflow.
Manages scaling, invocations, and health checks automatically.
"""

import json
import sys
import uuid
from pathlib import Path

from bedrock_agentcore import BedrockAgentCoreApp
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv()

from src.agents import OrchestratorAgent
from src.utils.logging_config import get_logger, setup_logging
from src.workflows import AIOpsSwarm, run_proactive_workflow

setup_logging()
logger = get_logger("main")

# Initialize AgentCore app
app = BedrockAgentCoreApp()


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
    """Handle proactive workflow mode."""
    logger.info("Running proactive workflow")

    result = run_proactive_workflow()

    services_total = result.get("services", {}).get("total", 0)
    tickets_count = len(result.get("tickets_created", []))
    execution_time = result.get("execution_time_seconds", 0)

    logger.info(
        "Workflow completed: "
        f"{services_total} services processed, "
        f"{tickets_count} tickets created, "
        f"{execution_time:.2f}s"
    )

    return result


def handle_chat(payload: dict) -> dict:
    """
    Handle interactive chat mode with session support.

    Uses the OrchestratorAgent for multi-turn conversations.
    AgentCore handles session persistence automatically.
    """
    message = payload.get("message", "")
    session_id = payload.get("session_id")

    if not message:
        return {"success": False, "error": "Missing 'message' in payload"}

    # Generate session_id if not provided (first interaction)
    is_new_session = False
    if not session_id:
        session_id = str(uuid.uuid4())
        is_new_session = True
        logger.info(f"New chat session created: {session_id}")
    else:
        logger.info(f"Continuing chat session: {session_id}")

    # Create orchestrator with session
    # AgentCore handles session persistence via its Memory service
    orchestrator = OrchestratorAgent(session_id=session_id)

    # Invoke the orchestrator with the user message
    logger.info(f"Processing chat message: {message[:100]}...")

    try:
        response = orchestrator.invoke(message)

        # Extract the response text
        response_text = str(response) if response else "No response generated"

        return {
            "success": True,
            "session_id": session_id,
            "is_new_session": is_new_session,
            "response": response_text,
        }

    except Exception as e:
        logger.error(f"Chat invocation failed: {e}")
        return {
            "success": False,
            "session_id": session_id,
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
