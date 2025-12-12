"""
AgentCore Application Entry Point

Main entry point for deploying the AIOps Multi-Agent System
on Amazon Bedrock AgentCore Runtime.
"""

import json
import os
import sys

# Add src to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

# Load environment variables from .env file (for local testing)
from dotenv import load_dotenv
load_dotenv()

from bedrock_agentcore import BedrockAgentCoreApp

from src.agents import OrchestratorAgent
from src.workflows import AIOpsSwarm, run_daily_analysis
from src.utils.logging_config import setup_logging, get_logger

# Initialize logging
setup_logging()
logger = get_logger("agentcore.app")

# Initialize the AgentCore app
app = BedrockAgentCoreApp()

# Global agent instances (lazily initialized)
_orchestrator = None
_swarm = None


def get_orchestrator(session_id: str = None) -> OrchestratorAgent:
    """Get or create the orchestrator agent."""
    global _orchestrator
    
    if _orchestrator is None or session_id:
        _orchestrator = OrchestratorAgent(
            session_id=session_id,
            use_s3_storage=True,
        )
    
    return _orchestrator


def get_swarm() -> AIOpsSwarm:
    """Get or create the swarm."""
    global _swarm
    
    if _swarm is None:
        _swarm = AIOpsSwarm()
    
    return _swarm


@app.entrypoint
def invoke(payload: dict) -> dict:
    """
    Main entry point for AgentCore invocations.
    
    Supports multiple operation modes:
    - chat: Interactive conversation with the orchestrator
    - analyze: Run full analysis workflow
    - swarm: Run task through multi-agent swarm
    - daily_report: Run daily cron analysis
    
    Payload structure:
    {
        "mode": "chat" | "analyze" | "swarm" | "daily_report",
        "prompt": "User message or task description",
        "session_id": "optional-session-id",
        "options": {
            "time_from": "now-1d",
            "time_to": "now",
            "create_tickets": true,
            "dry_run": false
        }
    }
    """
    logger.info(f"Received invocation: {json.dumps(payload)[:200]}...")
    
    # Extract parameters
    mode = payload.get("mode", "chat")
    prompt = payload.get("prompt", "")
    session_id = payload.get("session_id")
    options = payload.get("options", {})
    
    try:
        if mode == "chat":
            return handle_chat(prompt, session_id)
        
        elif mode == "analyze":
            return handle_analyze(prompt, options)
        
        elif mode == "swarm":
            return handle_swarm(prompt)
        
        elif mode == "daily_report":
            return handle_daily_report(options)
        
        else:
            return {
                "error": f"Unknown mode: {mode}",
                "supported_modes": ["chat", "analyze", "swarm", "daily_report"],
            }
            
    except Exception as e:
        logger.error(f"Invocation failed: {e}")
        return {
            "error": str(e),
            "mode": mode,
        }


def handle_chat(prompt: str, session_id: str = None) -> dict:
    """Handle interactive chat mode."""
    if not prompt:
        return {"error": "Missing 'prompt' in payload"}
    
    orchestrator = get_orchestrator(session_id)
    response = orchestrator.invoke(prompt)
    
    return {
        "mode": "chat",
        "response": response,
        "session_id": session_id,
        "actions": len(orchestrator.action_history),
    }


def handle_analyze(prompt: str, options: dict) -> dict:
    """Handle full analysis workflow mode."""
    orchestrator = get_orchestrator()
    
    time_from = options.get("time_from", "now-1d")
    time_to = options.get("time_to", "now")
    create_tickets = options.get("create_tickets", True)
    
    result = orchestrator.analyze_and_report(
        user_request=prompt or "Daily log analysis",
        time_from=time_from,
        time_to=time_to,
        create_tickets=create_tickets,
    )
    
    return {
        "mode": "analyze",
        "result": result,
        "report": orchestrator.generate_report(),
    }


def handle_swarm(prompt: str) -> dict:
    """Handle swarm execution mode."""
    if not prompt:
        return {"error": "Missing 'prompt' in payload"}
    
    swarm = get_swarm()
    result = swarm.run(prompt)
    
    return {
        "mode": "swarm",
        "success": result.success,
        "output": result.output,
        "summary": result.summary,
        "agents_used": result.agents_used,
        "error": result.error if not result.success else None,
    }


def handle_daily_report(options: dict) -> dict:
    """Handle daily report generation mode."""
    time_from = options.get("time_from", "now-1d")
    time_to = options.get("time_to", "now")
    create_tickets = options.get("create_tickets", True)
    dry_run = options.get("dry_run", False)
    
    result = run_daily_analysis(
        time_from=time_from,
        time_to=time_to,
        create_tickets=create_tickets,
        dry_run=dry_run,
    )
    
    return {
        "mode": "daily_report",
        "result": result,
    }


# Health check endpoint
@app.health_check
def health():
    """Health check endpoint for AgentCore."""
    return {"status": "healthy", "service": "aiops-multi-agent"}


if __name__ == "__main__":
    # Run the AgentCore application
    app.run()
