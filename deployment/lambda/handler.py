"""
Lambda Handler for Cron Job Execution

This handler is designed to be triggered by EventBridge (CloudWatch Events)
on a schedule (e.g., daily) to run the AIOps analysis workflow.
"""

import json
import os
import sys

# Add src to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

# Load environment variables from .env file (for local testing)
# In Lambda, env vars are set via Lambda configuration
from dotenv import load_dotenv
load_dotenv()

from src.workflows import DailyAnalysisWorkflow, run_daily_analysis
from src.utils.logging_config import setup_logging, get_logger

# Initialize logging
setup_logging()
logger = get_logger("lambda.handler")


def handler(event: dict, context) -> dict:
    """
    Lambda handler for scheduled cron job execution.
    
    Can be triggered by:
    - EventBridge scheduled rule (daily cron)
    - Direct invocation with custom parameters
    - Step Functions workflow
    
    Event structure for direct invocation:
    {
        "time_from": "now-1d",      # Optional, defaults to "now-1d"
        "time_to": "now",           # Optional, defaults to "now"
        "create_tickets": true,     # Optional, defaults to true
        "dry_run": false,           # Optional, defaults to false
        "min_severity": "medium"    # Optional, defaults to "medium"
    }
    
    EventBridge event structure:
    {
        "version": "0",
        "id": "...",
        "detail-type": "Scheduled Event",
        "source": "aws.events",
        ...
    }
    """
    logger.info(f"Lambda invoked with event: {json.dumps(event)[:500]}...")
    
    try:
        # Check if this is an EventBridge scheduled event
        if event.get("source") == "aws.events":
            # Scheduled event - use defaults
            logger.info("Processing scheduled EventBridge event")
            options = {}
        else:
            # Direct invocation - use provided options
            options = event
        
        # Extract parameters
        time_from = options.get("time_from", "now-1d")
        time_to = options.get("time_to", "now")
        create_tickets = options.get("create_tickets", True)
        dry_run = options.get("dry_run", False)
        min_severity = options.get("min_severity", "medium")
        
        # Create and execute workflow
        workflow = DailyAnalysisWorkflow(
            time_from=time_from,
            time_to=time_to,
            create_tickets=create_tickets,
            min_severity_for_ticket=min_severity,
            dry_run=dry_run,
        )
        
        result = workflow.execute()
        
        # Log summary
        logger.info(f"Workflow completed: {result.get('summary', 'No summary')[:200]}...")
        
        return {
            "statusCode": 200 if result.get("success") else 500,
            "body": json.dumps(result),
            "headers": {
                "Content-Type": "application/json",
            },
        }
        
    except Exception as e:
        logger.error(f"Lambda execution failed: {e}", exc_info=True)
        
        return {
            "statusCode": 500,
            "body": json.dumps({
                "success": False,
                "error": str(e),
            }),
            "headers": {
                "Content-Type": "application/json",
            },
        }


def interactive_handler(event: dict, context) -> dict:
    """
    Lambda handler for interactive agent invocations.
    
    This handler is for API Gateway integration to allow
    users to interact with the orchestrator agent.
    
    Event structure:
    {
        "body": "{\"prompt\": \"...\", \"session_id\": \"...\"}",
        "headers": {...},
        ...
    }
    """
    logger.info("Interactive handler invoked")
    
    try:
        # Parse body
        if isinstance(event.get("body"), str):
            body = json.loads(event["body"])
        else:
            body = event.get("body", {})
        
        prompt = body.get("prompt", "")
        session_id = body.get("session_id")
        
        if not prompt:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Missing 'prompt' in request body"}),
                "headers": {"Content-Type": "application/json"},
            }
        
        # Import here to avoid cold start overhead for cron handler
        from src.agents import OrchestratorAgent
        
        # Create orchestrator with session
        orchestrator = OrchestratorAgent(
            session_id=session_id,
            use_s3_storage=True if session_id else False,
        )
        
        # Invoke agent
        response = orchestrator.invoke(prompt)
        
        return {
            "statusCode": 200,
            "body": json.dumps({
                "response": response,
                "session_id": session_id,
                "actions": len(orchestrator.action_history),
            }),
            "headers": {
                "Content-Type": "application/json",
            },
        }
        
    except Exception as e:
        logger.error(f"Interactive handler failed: {e}", exc_info=True)
        
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)}),
            "headers": {"Content-Type": "application/json"},
        }
