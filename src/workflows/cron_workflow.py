"""
Cron Workflow Module

Implements the daily analysis workflow that runs as a scheduled job.
Fetches logs, analyzes issues, creates tickets, and generates reports.
"""

import json
from datetime import datetime, timezone
from typing import Any

from ..agents import DataDogAgent, CodingAgent, ServiceNowAgent, OrchestratorAgent
from ..utils.config_loader import get_config
from ..utils.logging_config import get_logger

logger = get_logger("workflows.cron")


class DailyAnalysisWorkflow:
    """
    Daily Analysis Workflow for scheduled execution.
    
    This workflow is designed to run as a cron job (e.g., daily via EventBridge)
    and performs the following:
    
    1. Fetch error/warning logs from DataDog (last 24 hours)
    2. Analyze logs with the Coding Agent to identify issues
    3. Create ServiceNow tickets for significant issues
    4. Generate a comprehensive report
    
    Usage:
        # Direct execution
        workflow = DailyAnalysisWorkflow()
        report = workflow.execute()
        
        # In Lambda handler
        def handler(event, context):
            workflow = DailyAnalysisWorkflow()
            return workflow.execute_for_lambda()
    """
    
    def __init__(
        self,
        time_from: str = "now-1d",
        time_to: str = "now",
        create_tickets: bool = True,
        min_severity_for_ticket: str = "medium",
        dry_run: bool = False,
    ):
        """
        Initialize the daily analysis workflow.
        
        Args:
            time_from: Start time for log query (DataDog time syntax).
            time_to: End time for log query.
            create_tickets: Whether to create ServiceNow tickets.
            min_severity_for_ticket: Minimum severity to create tickets.
            dry_run: If True, don't create actual tickets.
        """
        config = get_config()
        cron_config = config.settings.cron
        
        self._time_from = time_from or cron_config.default_time_from
        self._time_to = time_to or cron_config.default_time_to
        self._create_tickets = create_tickets
        self._min_severity = min_severity_for_ticket
        self._dry_run = dry_run or config.settings.features.dry_run_mode
        
        # Initialize agents
        self._datadog_agent = DataDogAgent()
        self._coding_agent = CodingAgent()
        self._servicenow_agent = ServiceNowAgent()
        
        # Workflow state
        self._start_time: datetime | None = None
        self._end_time: datetime | None = None
        self._results: dict = {}
        
        logger.info(
            f"Initialized DailyAnalysisWorkflow: "
            f"time_range={self._time_from} to {self._time_to}, "
            f"dry_run={self._dry_run}"
        )
    
    def execute(self) -> dict:
        """
        Execute the daily analysis workflow.
        
        Returns:
            Dictionary containing the complete workflow report.
        """
        self._start_time = datetime.now(timezone.utc)
        logger.info("Starting daily analysis workflow")
        
        try:
            # Step 1: Fetch logs from DataDog
            logs_result = self._fetch_logs()
            
            if not logs_result["logs"]:
                return self._build_empty_report("No logs found in the specified time range")
            
            # Step 2: Analyze logs for each service
            analysis_result = self._analyze_logs(logs_result)
            
            # Step 3: Create tickets for significant issues
            tickets_result = self._create_tickets_for_issues(analysis_result)
            
            # Step 4: Build final report
            report = self._build_report(logs_result, analysis_result, tickets_result)
            
            self._end_time = datetime.now(timezone.utc)
            self._results = report
            
            logger.info("Daily analysis workflow completed successfully")
            return report
            
        except Exception as e:
            self._end_time = datetime.now(timezone.utc)
            logger.error(f"Workflow failed: {e}")
            
            return {
                "success": False,
                "error": str(e),
                "execution_time": self._get_execution_time(),
                "timestamp": self._start_time.isoformat() if self._start_time else None,
            }
    
    def execute_for_lambda(self) -> dict:
        """
        Execute the workflow and return Lambda-compatible response.
        
        Returns:
            Dictionary with statusCode and body for Lambda response.
        """
        try:
            report = self.execute()
            
            return {
                "statusCode": 200 if report.get("success", False) else 500,
                "body": json.dumps(report),
                "headers": {
                    "Content-Type": "application/json",
                },
            }
            
        except Exception as e:
            logger.error(f"Lambda execution failed: {e}")
            
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
    
    def _fetch_logs(self) -> dict:
        """Fetch logs from DataDog."""
        logger.info(f"Fetching logs: {self._time_from} to {self._time_to}")
        
        logs = self._datadog_agent.fetch_logs(
            time_from=self._time_from,
            time_to=self._time_to,
        )
        
        services = self._datadog_agent.get_services(logs)
        
        return {
            "logs": logs,
            "services": services,
            "log_count": len(logs),
            "service_count": len(services),
        }
    
    def _analyze_logs(self, logs_result: dict) -> dict:
        """Analyze logs using the Coding Agent."""
        logger.info(f"Analyzing logs for {len(logs_result['services'])} services")
        
        analysis_by_service = {}
        
        for service in logs_result["services"]:
            # Format logs for this service
            formatted_logs = self._datadog_agent.format_logs(
                logs_result["logs"],
                service=service,
            )
            
            # Run full analysis
            analysis = self._coding_agent.full_analysis(
                log_context=formatted_logs,
                service_name=service,
            )
            
            analysis_by_service[service] = {
                "analysis": analysis,
                "formatted_logs": formatted_logs,
            }
            
            severity = analysis.get("severity", {}).get("severity", "unknown")
            logger.info(f"Analyzed {service}: severity={severity}")
        
        return {
            "by_service": analysis_by_service,
            "services_analyzed": len(analysis_by_service),
        }
    
    def _create_tickets_for_issues(self, analysis_result: dict) -> dict:
        """Create ServiceNow tickets for significant issues."""
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        min_severity_level = severity_order.get(self._min_severity, 2)
        
        tickets_created = []
        tickets_skipped = []
        
        for service, data in analysis_result["by_service"].items():
            analysis = data["analysis"]
            severity = analysis.get("severity", {}).get("severity", "low")
            severity_level = severity_order.get(severity, 3)
            
            if not self._create_tickets:
                tickets_skipped.append({
                    "service": service,
                    "reason": "Ticket creation disabled",
                })
                continue
            
            if severity_level > min_severity_level:
                tickets_skipped.append({
                    "service": service,
                    "severity": severity,
                    "reason": f"Below minimum severity ({self._min_severity})",
                })
                continue
            
            if self._dry_run:
                tickets_created.append({
                    "service": service,
                    "severity": severity,
                    "ticket_number": "DRY-RUN-XXXX",
                    "dry_run": True,
                })
                logger.info(f"[DRY RUN] Would create ticket for {service}")
                continue
            
            # Create the ticket
            ticket = self._servicenow_agent.create_ticket_from_analysis(
                service_name=service,
                analysis_report=analysis,
                log_context=data["formatted_logs"],
            )
            
            if "error" not in ticket:
                tickets_created.append({
                    "service": service,
                    "severity": severity,
                    "ticket_number": ticket.get("number"),
                    "sys_id": ticket.get("sys_id"),
                })
                logger.info(f"Created ticket {ticket.get('number')} for {service}")
            else:
                tickets_skipped.append({
                    "service": service,
                    "reason": f"Creation failed: {ticket.get('error')}",
                })
        
        return {
            "created": tickets_created,
            "skipped": tickets_skipped,
            "total_created": len(tickets_created),
            "total_skipped": len(tickets_skipped),
        }
    
    def _build_report(
        self,
        logs_result: dict,
        analysis_result: dict,
        tickets_result: dict,
    ) -> dict:
        """Build the final workflow report."""
        # Count issues by severity
        severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for service, data in analysis_result["by_service"].items():
            severity = data["analysis"].get("severity", {}).get("severity", "low")
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
        
        return {
            "success": True,
            "timestamp": self._start_time.isoformat() if self._start_time else None,
            "execution_time": self._get_execution_time(),
            "time_range": {
                "from": self._time_from,
                "to": self._time_to,
            },
            "logs": {
                "total_fetched": logs_result["log_count"],
                "services_found": logs_result["services"],
            },
            "analysis": {
                "services_analyzed": analysis_result["services_analyzed"],
                "severity_breakdown": severity_counts,
            },
            "tickets": {
                "created": tickets_result["total_created"],
                "skipped": tickets_result["total_skipped"],
                "details": tickets_result["created"],
            },
            "dry_run": self._dry_run,
            "summary": self._generate_text_summary(
                logs_result, analysis_result, tickets_result, severity_counts
            ),
        }
    
    def _build_empty_report(self, reason: str) -> dict:
        """Build a report for empty results."""
        return {
            "success": True,
            "timestamp": self._start_time.isoformat() if self._start_time else None,
            "execution_time": self._get_execution_time(),
            "time_range": {
                "from": self._time_from,
                "to": self._time_to,
            },
            "logs": {
                "total_fetched": 0,
                "services_found": [],
            },
            "analysis": {
                "services_analyzed": 0,
                "severity_breakdown": {},
            },
            "tickets": {
                "created": 0,
                "skipped": 0,
                "details": [],
            },
            "summary": reason,
        }
    
    def _generate_text_summary(
        self,
        logs_result: dict,
        analysis_result: dict,
        tickets_result: dict,
        severity_counts: dict,
    ) -> str:
        """Generate a human-readable summary."""
        lines = [
            "# Daily AIOps Analysis Report",
            "",
            f"**Execution Time:** {self._start_time.strftime('%Y-%m-%d %H:%M:%S UTC') if self._start_time else 'N/A'}",
            f"**Time Range:** {self._time_from} to {self._time_to}",
            "",
            "## Overview",
            f"- Logs analyzed: {logs_result['log_count']}",
            f"- Services affected: {len(logs_result['services'])}",
            f"- Tickets created: {tickets_result['total_created']}",
            "",
            "## Issues by Severity",
        ]
        
        for severity in ["critical", "high", "medium", "low"]:
            count = severity_counts.get(severity, 0)
            emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(severity, "⚪")
            lines.append(f"- {emoji} {severity.capitalize()}: {count}")
        
        lines.append("")
        
        if tickets_result["created"]:
            lines.append("## Tickets Created")
            for ticket in tickets_result["created"]:
                lines.append(
                    f"- **{ticket['ticket_number']}**: [{ticket['severity'].upper()}] {ticket['service']}"
                )
        
        if self._dry_run:
            lines.append("")
            lines.append("*Note: This was a dry run. No actual tickets were created.*")
        
        return "\n".join(lines)
    
    def _get_execution_time(self) -> str:
        """Get the execution time as a string."""
        if not self._start_time:
            return "N/A"
        
        end = self._end_time or datetime.now(timezone.utc)
        duration = end - self._start_time
        
        return f"{duration.total_seconds():.2f}s"


def run_daily_analysis(
    time_from: str = "now-1d",
    time_to: str = "now",
    create_tickets: bool = True,
    dry_run: bool = False,
) -> dict:
    """
    Convenience function to run the daily analysis workflow.
    
    Args:
        time_from: Start time for log query.
        time_to: End time for log query.
        create_tickets: Whether to create tickets.
        dry_run: Whether to run in dry-run mode.
        
    Returns:
        Workflow report dictionary.
    """
    workflow = DailyAnalysisWorkflow(
        time_from=time_from,
        time_to=time_to,
        create_tickets=create_tickets,
        dry_run=dry_run,
    )
    
    return workflow.execute()
