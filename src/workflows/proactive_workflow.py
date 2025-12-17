"""
Proactive Workflow Module

Implements the proactive analysis workflow that runs as an ECS task.
Fetches services with issues, processes them in parallel, creates tickets,
and uploads reports to S3.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime

from ..agents import CodingAgent, DataDogAgent, S3Agent, ServiceNowAgent
from ..utils.config_loader import load_settings
from ..utils.logging_config import get_logger

logger = get_logger("workflows.proactive")


@dataclass
class ServiceResult:
    """Result of processing a single service."""

    service_name: str
    success: bool
    severity: str
    ticket_number: str | None
    s3_uri: str | None
    error: str | None
    duration_seconds: float


class ServiceProcessor:
    """
    Lightweight processor for analyzing a single service (Option A).

    Uses agents directly without full orchestrator overhead.
    """

    def __init__(self):
        """Initialize the service processor with required agents."""
        self._coding_agent = CodingAgent()
        self._servicenow_agent = ServiceNowAgent()
        self._s3_agent = S3Agent()

    def process(
        self,
        service_name: str,
        formatted_logs: str,
        raw_logs: list[dict],
    ) -> ServiceResult:
        """
        Process a single service: analyze, create ticket, upload report.

        Args:
            service_name: Name of the service to process.
            formatted_logs: Pre-formatted log context.
            raw_logs: Raw log entries for the service.

        Returns:
            ServiceResult with processing outcome.
        """
        start_time = datetime.now(UTC)
        logger.info(f"Processing service: {service_name}")

        try:
            # Step 1: Analyze logs
            analysis = self._coding_agent.full_analysis(
                log_context=formatted_logs,
                service_name=service_name,
            )

            severity = analysis.get("severity", {}).get("severity", "low")

            # Step 2: Create ServiceNow ticket
            ticket_number = None
            if severity in ("critical", "high", "medium"):
                ticket = self._servicenow_agent.create_ticket_from_analysis(
                    service_name=service_name,
                    analysis_report=analysis,
                    log_context=formatted_logs,
                )
                if "error" not in ticket:
                    ticket_number = ticket.get("number")

            # Step 3: Generate and upload report
            report_content = self._generate_report(
                service_name=service_name,
                analysis=analysis,
                ticket_number=ticket_number,
                formatted_logs=formatted_logs,
            )

            upload_result = self._s3_agent.upload_report(service_name, report_content)
            s3_uri = upload_result.get("s3_uri") if upload_result.get("success") else None

            duration = (datetime.now(UTC) - start_time).total_seconds()

            return ServiceResult(
                service_name=service_name,
                success=True,
                severity=severity,
                ticket_number=ticket_number,
                s3_uri=s3_uri,
                error=None,
                duration_seconds=duration,
            )

        except Exception as e:
            duration = (datetime.now(UTC) - start_time).total_seconds()
            logger.error(f"Failed to process {service_name}: {e}")

            return ServiceResult(
                service_name=service_name,
                success=False,
                severity="unknown",
                ticket_number=None,
                s3_uri=None,
                error=str(e),
                duration_seconds=duration,
            )

    def _generate_report(
        self,
        service_name: str,
        analysis: dict,
        ticket_number: str | None,
        formatted_logs: str,
    ) -> str:
        """Generate a clean markdown report for a service."""
        severity = analysis.get("severity", {})
        patterns = analysis.get("patterns", {})
        suggestions = analysis.get("suggestions", [])

        lines = [
            f"# Error Report: {service_name}",
            "",
            f"Generated: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}",
            "",
            "## Summary",
            f"- Severity: {severity.get('severity', 'unknown').upper()}",
            f"- Error types: {len(patterns.get('error_types', []))}",
            f"- Recurring issues: {len(patterns.get('recurring_issues', []))}",
        ]

        if ticket_number:
            lines.append(f"- ServiceNow ticket: {ticket_number}")

        lines.append("")

        # Error types
        if patterns.get("error_types"):
            lines.append("## Errors Detected")
            for error_type in patterns["error_types"]:
                lines.append(f"- {error_type}")
            lines.append("")

        # Potential causes
        if patterns.get("potential_causes"):
            lines.append("## Root Cause Analysis")
            for cause in patterns["potential_causes"]:
                lines.append(f"- {cause}")
            lines.append("")

        # Suggested fixes
        if suggestions:
            lines.append("## Suggested Fixes")
            for i, suggestion in enumerate(suggestions, 1):
                lines.append(f"### {i}. {suggestion.get('error_type', 'General')}")
                lines.append(f"**Issue:** {suggestion.get('issue', 'N/A')}")
                lines.append(f"**Fix:** {suggestion.get('suggestion', 'N/A')}")
                if suggestion.get("prevention"):
                    lines.append(f"**Prevention:** {suggestion['prevention']}")
                lines.append("")

        # Log context
        if formatted_logs:
            lines.append("## Related Logs")
            lines.append("```")
            # Limit to first 50 lines
            log_lines = formatted_logs.split("\n")[:50]
            lines.extend(log_lines)
            if len(formatted_logs.split("\n")) > 50:
                lines.append("... (truncated)")
            lines.append("```")

        return "\n".join(lines)


class OrchestratorProcessor:
    """
    Full orchestrator-based processor for a single service (Option B).

    Uses the OrchestratorAgent for each service with full LLM reasoning.
    """

    def __init__(self):
        """Initialize with required agents."""
        # Import here to avoid circular dependency
        from ..agents import OrchestratorAgent

        self._OrchestratorAgent = OrchestratorAgent
        self._s3_agent = S3Agent()

    def process(
        self,
        service_name: str,
        formatted_logs: str,
        raw_logs: list[dict],
    ) -> ServiceResult:
        """
        Process a single service using full orchestrator.

        Args:
            service_name: Name of the service to process.
            formatted_logs: Pre-formatted log context.
            raw_logs: Raw log entries for the service.

        Returns:
            ServiceResult with processing outcome.
        """
        start_time = datetime.now(UTC)
        logger.info(f"Processing service with orchestrator: {service_name}")

        try:
            # Create orchestrator for this service
            orchestrator = self._OrchestratorAgent(
                session_id=f"proactive-{service_name}-{start_time.strftime('%Y%m%d%H%M%S')}",
                use_s3_storage=False,
            )

            # Invoke orchestrator with analysis request
            prompt = f"""Analyze the following logs for service '{service_name}' and:
1. Identify error patterns and root causes
2. Assess severity
3. Suggest fixes
4. Create a ServiceNow ticket if severity is medium or higher

Logs:
{formatted_logs}"""

            response = orchestrator.invoke(prompt)

            # Get analysis from orchestrator's sub-agents
            severity = "medium"  # Default
            ticket_number = None

            # Check if ticket was created
            if orchestrator._servicenow_agent:
                for action in orchestrator._servicenow_agent.action_history:
                    if action.action_type == "create_ticket" and action.success:
                        ticket_number = action.output_summary.split(":")[-1].strip()
                        break

            # Check severity from coding agent
            if orchestrator._coding_agent:
                for action in orchestrator._coding_agent.action_history:
                    if "severity" in action.output_summary.lower():
                        if "critical" in action.output_summary.lower():
                            severity = "critical"
                        elif "high" in action.output_summary.lower():
                            severity = "high"
                        elif "medium" in action.output_summary.lower():
                            severity = "medium"
                        else:
                            severity = "low"
                        break

            # Generate and upload report
            report_content = self._generate_report(
                service_name=service_name,
                response=response,
                ticket_number=ticket_number,
                severity=severity,
            )

            upload_result = self._s3_agent.upload_report(service_name, report_content)
            s3_uri = upload_result.get("s3_uri") if upload_result.get("success") else None

            duration = (datetime.now(UTC) - start_time).total_seconds()

            return ServiceResult(
                service_name=service_name,
                success=True,
                severity=severity,
                ticket_number=ticket_number,
                s3_uri=s3_uri,
                error=None,
                duration_seconds=duration,
            )

        except Exception as e:
            duration = (datetime.now(UTC) - start_time).total_seconds()
            logger.error(f"Failed to process {service_name}: {e}")

            return ServiceResult(
                service_name=service_name,
                success=False,
                severity="unknown",
                ticket_number=None,
                s3_uri=None,
                error=str(e),
                duration_seconds=duration,
            )

    def _generate_report(
        self,
        service_name: str,
        response: str,
        ticket_number: str | None,
        severity: str,
    ) -> str:
        """Generate a clean markdown report from orchestrator response."""
        lines = [
            f"# Error Report: {service_name}",
            "",
            f"Generated: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}",
            "",
            "## Summary",
            f"- Severity: {severity.upper()}",
        ]

        if ticket_number:
            lines.append(f"- ServiceNow ticket: {ticket_number}")

        lines.extend([
            "",
            "## Analysis",
            "",
            response,
        ])

        return "\n".join(lines)


class ProactiveWorkflow:
    """
    Proactive Analysis Workflow for ECS execution.

    This workflow is triggered by EventBridge and:
    1. Fetches all services with errors/warnings from DataDog
    2. Processes each service in parallel using ThreadPoolExecutor
    3. Creates ServiceNow tickets for significant issues
    4. Uploads individual reports to S3
    5. Generates and uploads a summary report
    """

    def __init__(self):
        """Initialize the proactive workflow."""
        settings = load_settings()
        workflow_config = settings.get("workflow", {})

        self._time_from = workflow_config.get("default_time_from", "now-1d")
        self._time_to = workflow_config.get("default_time_to", "now")
        self._max_workers = workflow_config.get("max_workers", 50)
        self._use_lightweight = workflow_config.get("use_lightweight_processor", False)

        # Initialize DataDog agent for fetching logs
        self._datadog_agent = DataDogAgent()
        self._s3_agent = S3Agent()

        # Workflow state
        self._start_time: datetime | None = None
        self._end_time: datetime | None = None
        self._results: list[ServiceResult] = []

        logger.info(
            f"Initialized ProactiveWorkflow: "
            f"max_workers={self._max_workers}, "
            f"lightweight={self._use_lightweight}"
        )

    def run(self) -> dict:
        """
        Execute the proactive workflow.

        Returns:
            Dictionary containing the complete workflow report.
        """
        self._start_time = datetime.now(UTC)
        logger.info("Starting proactive workflow")

        try:
            # Step 1: Fetch all logs and identify affected services
            logs, services = self._fetch_affected_services()

            if not services:
                logger.info("No services with issues found")
                return self._build_report([])

            logger.info(f"Found {len(services)} services with issues")

            # Step 2: Prepare data for each service
            service_data = self._prepare_service_data(logs, services)

            # Step 3: Process services in parallel
            results = self._process_services_parallel(service_data)

            # Step 4: Generate and upload summary
            self._upload_summary(results)

            # Step 5: Build final report
            self._end_time = datetime.now(UTC)
            return self._build_report(results)

        except Exception as e:
            self._end_time = datetime.now(UTC)
            logger.error(f"Workflow failed: {e}")

            return {
                "success": False,
                "error": str(e),
                "execution_time_seconds": self._get_execution_time(),
                "timestamp": self._start_time.isoformat() if self._start_time else None,
            }

    def _fetch_affected_services(self) -> tuple[list[dict], list[str]]:
        """Fetch logs and extract affected services."""
        logger.info(f"Fetching logs: {self._time_from} to {self._time_to}")

        logs = self._datadog_agent.fetch_logs(
            time_from=self._time_from,
            time_to=self._time_to,
        )

        services = self._datadog_agent.get_services(logs)

        return logs, services

    def _prepare_service_data(
        self,
        logs: list[dict],
        services: list[str],
    ) -> list[dict]:
        """Prepare log data for each service."""
        service_data = []

        for service in services:
            # Filter logs for this service
            service_logs = [
                log
                for log in logs
                if log.get("attributes", {}).get("service") == service
            ]

            # Format logs
            formatted = self._datadog_agent.format_logs(logs, service=service)

            service_data.append({
                "service_name": service,
                "formatted_logs": formatted,
                "raw_logs": service_logs,
            })

        return service_data

    def _process_services_parallel(
        self,
        service_data: list[dict],
    ) -> list[ServiceResult]:
        """Process all services in parallel using ThreadPoolExecutor."""
        results = []

        # Create processor based on configuration
        if self._use_lightweight:
            logger.info("Using lightweight processor (Option A)")
            processor = ServiceProcessor()
        else:
            logger.info("Using orchestrator processor (Option B)")
            processor = OrchestratorProcessor()

        with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
            # Submit all tasks
            future_to_service = {
                executor.submit(
                    processor.process,
                    data["service_name"],
                    data["formatted_logs"],
                    data["raw_logs"],
                ): data["service_name"]
                for data in service_data
            }

            # Collect results as they complete
            for future in as_completed(future_to_service):
                service_name = future_to_service[future]
                try:
                    result = future.result()
                    results.append(result)
                    logger.info(
                        f"Completed {service_name}: "
                        f"success={result.success}, "
                        f"severity={result.severity}"
                    )
                except Exception as e:
                    logger.error(f"Failed to process {service_name}: {e}")
                    results.append(
                        ServiceResult(
                            service_name=service_name,
                            success=False,
                            severity="unknown",
                            ticket_number=None,
                            s3_uri=None,
                            error=str(e),
                            duration_seconds=0,
                        )
                    )

        return results

    def _upload_summary(self, results: list[ServiceResult]) -> None:
        """Generate and upload the summary report."""
        summary_content = self._generate_summary(results)
        upload_result = self._s3_agent.upload_summary(summary_content)

        if upload_result.get("success"):
            logger.info(f"Summary uploaded: {upload_result.get('s3_uri')}")
        else:
            logger.error(f"Failed to upload summary: {upload_result.get('error')}")

    def _generate_summary(self, results: list[ServiceResult]) -> str:
        """Generate a clean summary report."""
        now = datetime.now(UTC)
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]

        # Count by severity
        severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for r in successful:
            if r.severity in severity_counts:
                severity_counts[r.severity] += 1

        tickets_created = [r for r in successful if r.ticket_number]

        lines = [
            "# Proactive Analysis Summary",
            "",
            f"Generated: {now.strftime('%Y-%m-%d %H:%M:%S UTC')}",
            f"Time range: {self._time_from} to {self._time_to}",
            "",
            "## Overview",
            f"- Services processed: {len(results)}",
            f"- Successful: {len(successful)}",
            f"- Failed: {len(failed)}",
            f"- Tickets created: {len(tickets_created)}",
            "",
            "## Severity Breakdown",
            f"- Critical: {severity_counts['critical']}",
            f"- High: {severity_counts['high']}",
            f"- Medium: {severity_counts['medium']}",
            f"- Low: {severity_counts['low']}",
            "",
        ]

        if tickets_created:
            lines.append("## Tickets Created")
            for r in tickets_created:
                lines.append(f"- {r.ticket_number}: {r.service_name} ({r.severity.upper()})")
            lines.append("")

        if successful:
            lines.append("## Service Reports")
            for r in successful:
                status = f"[{r.severity.upper()}]"
                ticket_info = f" - Ticket: {r.ticket_number}" if r.ticket_number else ""
                lines.append(f"- {r.service_name} {status}{ticket_info}")
                if r.s3_uri:
                    lines.append(f"  Report: {r.s3_uri}")
            lines.append("")

        if failed:
            lines.append("## Failed Services")
            for r in failed:
                lines.append(f"- {r.service_name}: {r.error}")
            lines.append("")

        execution_time = self._get_execution_time()
        lines.append(f"Total execution time: {execution_time:.2f} seconds")

        return "\n".join(lines)

    def _build_report(self, results: list[ServiceResult]) -> dict:
        """Build the final workflow report dictionary."""
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]

        severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for r in successful:
            if r.severity in severity_counts:
                severity_counts[r.severity] += 1

        return {
            "success": True,
            "timestamp": self._start_time.isoformat() if self._start_time else None,
            "execution_time_seconds": self._get_execution_time(),
            "time_range": {
                "from": self._time_from,
                "to": self._time_to,
            },
            "services": {
                "total": len(results),
                "successful": len(successful),
                "failed": len(failed),
            },
            "severity_breakdown": severity_counts,
            "tickets_created": [
                {"service": r.service_name, "ticket": r.ticket_number, "severity": r.severity}
                for r in successful
                if r.ticket_number
            ],
            "reports_uploaded": [
                {"service": r.service_name, "s3_uri": r.s3_uri}
                for r in successful
                if r.s3_uri
            ],
            "errors": [
                {"service": r.service_name, "error": r.error}
                for r in failed
            ],
        }

    def _get_execution_time(self) -> float:
        """Get the execution time in seconds."""
        if not self._start_time:
            return 0

        end = self._end_time or datetime.now(UTC)
        return (end - self._start_time).total_seconds()


def run_proactive_workflow() -> dict:
    """
    Convenience function to run the proactive workflow.

    Returns:
        Workflow report dictionary.
    """
    workflow = ProactiveWorkflow()
    return workflow.run()
