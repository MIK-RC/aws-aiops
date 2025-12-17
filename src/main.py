"""
Main Entry Point

Entry point for the AIOps Proactive Workflow.
Triggered by AWS EventBridge, runs analysis and exits.
"""

import json
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv()

from src.utils.logging_config import get_logger, setup_logging
from src.workflows import run_proactive_workflow

setup_logging()
logger = get_logger("main")


def main():
    """
    Main entry point.

    Executes the proactive workflow:
    1. Fetches services with errors/warnings from DataDog
    2. Processes each service in parallel
    3. Creates ServiceNow tickets for significant issues
    4. Uploads reports to S3
    5. Generates summary and exits
    """
    logger.info("Starting AIOps Proactive Workflow")

    try:
        result = run_proactive_workflow()

        # Log summary
        services_total = result.get("services", {}).get("total", 0)
        tickets_count = len(result.get("tickets_created", []))
        execution_time = result.get("execution_time_seconds", 0)

        logger.info(
            f"Workflow completed: "
            f"{services_total} services processed, "
            f"{tickets_count} tickets created, "
            f"{execution_time:.2f}s"
        )

        # Print result for container logs
        print(json.dumps(result, indent=2))

        return 0 if result.get("success") else 1

    except Exception as e:
        logger.error(f"Workflow failed: {e}")
        print(json.dumps({"success": False, "error": str(e)}, indent=2))
        return 1


if __name__ == "__main__":
    sys.exit(main())
