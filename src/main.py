"""
Main Entry Point

Command-line interface for the AIOps Multi-Agent System.
Provides local testing and development capabilities.
"""

import argparse
import json
import sys
from pathlib import Path

# Add project root to path for direct script execution
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv()

from src.agents import OrchestratorAgent, DataDogAgent, CodingAgent, ServiceNowAgent
from src.workflows import AIOpsSwarm, run_daily_analysis
from src.utils.logging_config import setup_logging, get_logger

logger = get_logger("main")


def main():
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description="AIOps Multi-Agent System CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive chat with orchestrator
  python src/main.py chat "Analyze errors in the payment service"
  
  # Run daily analysis
  python src/main.py analyze --time-from now-1d --create-tickets
  
  # Run swarm task
  python src/main.py swarm "Investigate database connection issues"
  
  # Test individual agents
  python src/main.py test-agent datadog
        """,
    )

    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Chat command
    chat_parser = subparsers.add_parser("chat", help="Interactive chat with orchestrator")
    chat_parser.add_argument("prompt", help="Message to send to the orchestrator")
    chat_parser.add_argument("--session-id", help="Session ID for conversation persistence")

    # Analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Run analysis workflow")
    analyze_parser.add_argument("--time-from", default="now-1d", help="Start time (default: now-1d)")
    analyze_parser.add_argument("--time-to", default="now", help="End time (default: now)")
    analyze_parser.add_argument("--create-tickets", action="store_true", help="Create ServiceNow tickets")
    analyze_parser.add_argument("--dry-run", action="store_true", help="Dry run mode")

    # Swarm command
    swarm_parser = subparsers.add_parser("swarm", help="Run task through agent swarm")
    swarm_parser.add_argument("task", help="Task description for the swarm")

    # Test agent command
    test_parser = subparsers.add_parser("test-agent", help="Test individual agent")
    test_parser.add_argument(
        "agent",
        choices=["datadog", "coding", "servicenow", "orchestrator"],
        help="Agent to test",
    )
    test_parser.add_argument("--prompt", help="Custom prompt for testing")

    # Daily report command
    daily_parser = subparsers.add_parser("daily-report", help="Run daily analysis report")
    daily_parser.add_argument("--dry-run", action="store_true", help="Dry run mode")

    args = parser.parse_args()

    # Setup logging
    setup_logging(level=args.log_level)

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    try:
        if args.command == "chat":
            result = cmd_chat(args.prompt, args.session_id)
        elif args.command == "analyze":
            result = cmd_analyze(
                args.time_from,
                args.time_to,
                args.create_tickets,
                args.dry_run,
            )
        elif args.command == "swarm":
            result = cmd_swarm(args.task)
        elif args.command == "test-agent":
            result = cmd_test_agent(args.agent, args.prompt)
        elif args.command == "daily-report":
            result = cmd_daily_report(args.dry_run)
        else:
            parser.print_help()
            sys.exit(1)

        # Print result
        if isinstance(result, dict):
            print(json.dumps(result, indent=2))
        else:
            print(result)

    except KeyboardInterrupt:
        print("\nOperation cancelled")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Command failed: {e}")
        sys.exit(1)


def cmd_chat(prompt: str, session_id: str = None) -> str:
    """Handle chat command."""
    logger.info(f"Starting chat: {prompt[:50]}...")

    orchestrator = OrchestratorAgent(
        session_id=session_id,
        use_s3_storage=False,
        storage_dir="./sessions",
    )

    response = orchestrator.invoke(prompt)

    print("\n" + "=" * 60)
    print("ORCHESTRATOR RESPONSE")
    print("=" * 60)

    return response


def cmd_analyze(
    time_from: str,
    time_to: str,
    create_tickets: bool,
    dry_run: bool,
) -> dict:
    """Handle analyze command."""
    logger.info(f"Starting analysis: {time_from} to {time_to}")

    result = run_daily_analysis(
        time_from=time_from,
        time_to=time_to,
        create_tickets=create_tickets,
        dry_run=dry_run,
    )

    print("\n" + "=" * 60)
    print("ANALYSIS REPORT")
    print("=" * 60)
    print(result.get("summary", "No summary available"))
    print("=" * 60)

    return result


def cmd_swarm(task: str) -> dict:
    """Handle swarm command."""
    logger.info(f"Starting swarm task: {task[:50]}...")

    swarm = AIOpsSwarm()
    result = swarm.run(task)

    print("\n" + "=" * 60)
    print("SWARM RESULT")
    print("=" * 60)
    print(result.summary)
    print("=" * 60)

    return result.to_dict()


def cmd_test_agent(agent_name: str, prompt: str = None) -> str:
    """Handle test-agent command."""
    logger.info(f"Testing agent: {agent_name}")

    # Default test prompts
    default_prompts = {
        "datadog": "Fetch the last hour of error logs",
        "coding": "Analyze this error: NullPointerException at line 42",
        "servicenow": "Create a test ticket for database issues",
        "orchestrator": "What services have errors in the last 24 hours?",
    }

    test_prompt = prompt or default_prompts.get(agent_name, "Hello")

    # Create agent
    agent_classes = {
        "datadog": DataDogAgent,
        "coding": CodingAgent,
        "servicenow": ServiceNowAgent,
        "orchestrator": OrchestratorAgent,
    }

    agent_class = agent_classes.get(agent_name)
    if not agent_class:
        return f"Unknown agent: {agent_name}"

    agent = agent_class()

    print(f"\n{'=' * 60}")
    print(f"TESTING {agent_name.upper()} AGENT")
    print(f"Prompt: {test_prompt}")
    print("=" * 60)

    response = agent.invoke(test_prompt)

    print("\nResponse:")
    print(response)

    print("\nAction History:")
    print(agent.get_action_summary())

    return response


def cmd_daily_report(dry_run: bool) -> dict:
    """Handle daily-report command."""
    logger.info("Running daily report")

    result = run_daily_analysis(
        time_from="now-1d",
        time_to="now",
        create_tickets=True,
        dry_run=dry_run,
    )

    print("\n" + "=" * 60)
    print("DAILY REPORT")
    print("=" * 60)
    print(result.get("summary", "No summary available"))
    print("=" * 60)

    return result


if __name__ == "__main__":
    main()
