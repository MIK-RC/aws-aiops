#!/usr/bin/env python3
"""
Local Run Script

Utility script for running and testing the AIOps Multi-Agent System locally.
"""

import os
import sys

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv(os.path.join(project_root, ".env"))

from src.utils.logging_config import setup_logging
from src.agents import OrchestratorAgent, DataDogAgent, CodingAgent, ServiceNowAgent
from src.workflows import AIOpsSwarm, run_daily_analysis


def run_interactive():
    """Run interactive session with orchestrator."""
    setup_logging(level="INFO")
    
    print("=" * 60)
    print("AIOps Multi-Agent System - Interactive Mode")
    print("=" * 60)
    print("Type 'quit' or 'exit' to end the session")
    print("Type 'report' to get action summary")
    print("Type 'reset' to reset agent state")
    print()
    
    orchestrator = OrchestratorAgent(
        session_id="interactive-session",
        use_s3_storage=False,
        storage_dir="./sessions",
    )
    
    while True:
        try:
            user_input = input("\n> ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ("quit", "exit"):
                print("Goodbye!")
                break
            
            if user_input.lower() == "report":
                print(orchestrator.generate_report())
                continue
            
            if user_input.lower() == "reset":
                orchestrator.reset_all_agents()
                print("All agents reset.")
                continue
            
            response = orchestrator.invoke(user_input)
            print(f"\n{response}")
            
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break


def test_standalone_agents():
    """Test each agent independently."""
    setup_logging(level="INFO")
    
    print("=" * 60)
    print("Testing Standalone Agent Usage")
    print("=" * 60)
    
    # Test DataDog Agent
    print("\n--- DataDog Agent ---")
    datadog = DataDogAgent()
    summary = datadog.get_daily_error_summary()
    print(f"Daily summary: {summary}")
    
    # Test Coding Agent
    print("\n--- Coding Agent ---")
    coding = CodingAgent()
    sample_log = """
    [2024-01-15T10:30:00] [ERROR] [payment-api] NullPointerException at PaymentService.java:142
    [2024-01-15T10:31:00] [ERROR] [payment-api] Connection refused to database
    [2024-01-15T10:32:00] [WARN] [payment-api] Retry attempt 3 failed
    """
    analysis = coding.full_analysis(sample_log, "payment-api")
    print(f"Analysis: {analysis.get('summary', 'N/A')}")
    
    # Test ServiceNow Agent
    print("\n--- ServiceNow Agent ---")
    servicenow = ServiceNowAgent()
    # Note: This would create a real ticket if ServiceNow is configured
    print("ServiceNow agent initialized (ticket creation skipped)")
    print(f"Agent state: {servicenow.state}")


def run_daily_workflow():
    """Run the daily analysis workflow."""
    setup_logging(level="INFO")
    
    print("=" * 60)
    print("Running Daily Analysis Workflow (Dry Run)")
    print("=" * 60)
    
    result = run_daily_analysis(
        time_from="now-1d",
        time_to="now",
        create_tickets=True,
        dry_run=True,  # Dry run - no actual tickets
    )
    
    print(result.get("summary", "No summary"))


def run_swarm():
    """Run the multi-agent swarm."""
    setup_logging(level="INFO")
    
    print("=" * 60)
    print("Running Multi-Agent Swarm")
    print("=" * 60)
    
    swarm = AIOpsSwarm()
    
    task = "Analyze yesterday's error logs and identify the most critical issues"
    print(f"Task: {task}")
    
    result = swarm.run(task)
    
    print(f"\nSuccess: {result.success}")
    print(f"Agents used: {result.agents_used}")
    print(f"\nSummary:\n{result.summary}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Local run script")
    parser.add_argument(
        "mode",
        choices=["interactive", "test-agents", "daily", "swarm"],
        help="Run mode",
    )
    
    args = parser.parse_args()
    
    if args.mode == "interactive":
        run_interactive()
    elif args.mode == "test-agents":
        test_standalone_agents()
    elif args.mode == "daily":
        run_daily_workflow()
    elif args.mode == "swarm":
        run_swarm()
