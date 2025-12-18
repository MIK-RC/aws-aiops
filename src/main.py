"""
Main Entry Point

AgentCore Runtime wrapper for the AIOps Proactive Workflow.
Manages scaling, invocations, and health checks automatically.
"""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv()

from bedrock_agentcore import BedrockAgentCoreApp

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
    - "chat": Interactive chat with session support
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
        elif mode == "swarm":
            return handle_swarm(payload)
        else:
            return {
                "success": False,
                "error": f"Unknown mode: {mode}",
                "supported_modes": ["proactive", "swarm"],
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


# Support direct execution for local testing
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="AIOps Proactive Workflow")
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Start the AgentCore server (for container deployment)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port for the server (default: 8080)",
    )
    parser.add_argument(
        "--mode",
        choices=["proactive", "swarm"],
        default="proactive",
        help="Mode to run (default: proactive)",
    )
    parser.add_argument(
        "--task",
        type=str,
        default="",
        help="Task for swarm mode",
    )
    args = parser.parse_args()

    if args.serve:
        # Start the AgentCore server (for container deployment)
        logger.info(f"Starting AgentCore server on port {args.port}")
        app.run(port=args.port)
    else:
        # Run workflow directly (for local testing)
        payload = {"mode": args.mode}
        if args.task:
            payload["task"] = args.task
        result = invoke(payload)
        print(json.dumps(result, indent=2))
        sys.exit(0 if result.get("success") else 1)
