"""
Orchestrator Agent Module

Central coordinator agent that manages all specialist agents and user interactions.
Maintains conversation history and generates comprehensive reports.
"""

from strands.session import S3SessionManager, FileSessionManager

from .base import BaseAgent, AgentAction
from .datadog_agent import DataDogAgent
from .coding_agent import CodingAgent
from .servicenow_agent import ServiceNowAgent
from ..utils.config_loader import get_config


class OrchestratorAgent(BaseAgent):
    """
    Orchestrator Agent - Central coordinator for the AIOps system.
    
    Responsibilities:
    - Coordinate specialist agents (DataDog, Coding, ServiceNow)
    - Maintain conversation history and user context
    - Generate comprehensive reports of all agent actions
    - Manage the overall workflow for issue resolution
    
    The orchestrator can operate in two modes:
    1. Standalone: Direct user interaction with manual agent coordination
    2. Swarm: Automated multi-agent coordination via Strands Swarm
    
    Standalone Usage:
        orchestrator = OrchestratorAgent()
        
        # User interaction
        result = orchestrator.invoke("Analyze errors in the payment service")
        
        # Get report of all actions
        report = orchestrator.generate_report()
    
    With Memory Persistence:
        orchestrator = OrchestratorAgent(
            session_id="user-123-session",
            use_s3_storage=True,
            s3_bucket="my-sessions-bucket"
        )
    """
    
    def __init__(
        self,
        model_id: str | None = None,
        region: str | None = None,
        session_id: str | None = None,
        use_s3_storage: bool = False,
        s3_bucket: str | None = None,
        s3_prefix: str = "sessions/",
        storage_dir: str | None = None,
    ):
        """
        Initialize the Orchestrator Agent.
        
        Args:
            model_id: Optional Bedrock model ID override.
            region: Optional AWS region override.
            session_id: Session ID for conversation persistence.
            use_s3_storage: Whether to use S3 for session storage.
            s3_bucket: S3 bucket name (required if use_s3_storage=True).
            s3_prefix: S3 key prefix for session data.
            storage_dir: Local directory for file-based session storage.
        """
        # Create session manager if session_id provided
        session_manager = None
        if session_id:
            session_manager = self._create_session_manager(
                session_id=session_id,
                use_s3=use_s3_storage,
                s3_bucket=s3_bucket,
                s3_prefix=s3_prefix,
                storage_dir=storage_dir,
            )
        
        # Initialize specialist agents (lazy loaded)
        self._datadog_agent: DataDogAgent | None = None
        self._coding_agent: CodingAgent | None = None
        self._servicenow_agent: ServiceNowAgent | None = None
        
        # Store all agent reports for final summary
        self._agent_reports: list[dict] = []
        
        super().__init__(
            agent_type="orchestrator",
            model_id=model_id,
            region=region,
            session_manager=session_manager,
        )
    
    def _create_session_manager(
        self,
        session_id: str,
        use_s3: bool,
        s3_bucket: str | None,
        s3_prefix: str,
        storage_dir: str | None,
    ):
        """Create the appropriate session manager."""
        config = get_config().settings.session
        
        if use_s3:
            bucket = s3_bucket or config.bucket
            prefix = s3_prefix or config.prefix
            
            self._logger.info(f"Using S3 session storage: s3://{bucket}/{prefix}")
            return S3SessionManager(
                session_id=session_id,
                bucket=bucket,
                prefix=prefix,
            )
        else:
            directory = storage_dir or "./sessions"
            self._logger.info(f"Using file session storage: {directory}")
            return FileSessionManager(
                session_id=session_id,
                storage_dir=directory,
            )
    
    def get_tools(self) -> list:
        """
        Get the orchestrator's tools.
        
        The orchestrator primarily uses specialist agents rather than
        direct tools, but may have utility tools for reporting.
        """
        # Import here to avoid circular dependency
        from ..tools.datadog_tools import query_logs
        from ..tools.servicenow_tools import create_incident
        from ..tools.code_analysis_tools import analyze_error_patterns
        
        # The orchestrator can access high-level tools from all agents
        return [
            query_logs,
            analyze_error_patterns,
            create_incident,
        ]
    
    # ==========================================
    # Specialist Agent Access
    # ==========================================
    
    @property
    def datadog_agent(self) -> DataDogAgent:
        """Get or create the DataDog agent."""
        if self._datadog_agent is None:
            self._datadog_agent = DataDogAgent()
        return self._datadog_agent
    
    @property
    def coding_agent(self) -> CodingAgent:
        """Get or create the Coding agent."""
        if self._coding_agent is None:
            self._coding_agent = CodingAgent()
        return self._coding_agent
    
    @property
    def servicenow_agent(self) -> ServiceNowAgent:
        """Get or create the ServiceNow agent."""
        if self._servicenow_agent is None:
            self._servicenow_agent = ServiceNowAgent()
        return self._servicenow_agent
    
    # ==========================================
    # Workflow Methods
    # ==========================================
    
    def analyze_and_report(
        self,
        user_request: str,
        time_from: str = "now-1d",
        time_to: str = "now",
        create_tickets: bool = True,
    ) -> dict:
        """
        Complete workflow: fetch logs, analyze, and create tickets.
        
        This method orchestrates the full AIOps workflow:
        1. Fetch error/warning logs from DataDog
        2. Identify affected services
        3. Analyze errors with the Coding Agent
        4. Create tickets for issues via ServiceNow Agent
        5. Generate comprehensive report
        
        Args:
            user_request: The user's request or context.
            time_from: Start time for log query.
            time_to: End time for log query.
            create_tickets: Whether to create ServiceNow tickets.
            
        Returns:
            Complete workflow report.
        """
        self._logger.info(f"Starting full analysis workflow for: {user_request[:100]}")
        self._agent_reports = []
        
        workflow_result = {
            "user_request": user_request,
            "time_range": {"from": time_from, "to": time_to},
            "stages": {},
            "tickets_created": [],
            "summary": "",
        }
        
        # Stage 1: Fetch logs from DataDog
        self._logger.info("Stage 1: Fetching logs from DataDog")
        logs = self.datadog_agent.fetch_logs(
            time_from=time_from,
            time_to=time_to,
        )
        services = self.datadog_agent.get_services(logs)
        
        workflow_result["stages"]["datadog"] = {
            "logs_fetched": len(logs),
            "services_found": services,
        }
        
        self._agent_reports.append({
            "agent": "DataDog Agent",
            "action": "Fetched logs",
            "result": f"Retrieved {len(logs)} logs from {len(services)} services",
        })
        
        if not logs:
            workflow_result["summary"] = "No error/warning logs found in the specified time range."
            return workflow_result
        
        # Stage 2: Analyze each service's logs
        self._logger.info("Stage 2: Analyzing logs with Coding Agent")
        analysis_results = {}
        
        for service in services:
            formatted_logs = self.datadog_agent.format_logs(logs, service=service)
            analysis = self.coding_agent.full_analysis(formatted_logs, service_name=service)
            analysis_results[service] = analysis
            
            self._agent_reports.append({
                "agent": "Coding Agent",
                "action": f"Analyzed {service}",
                "result": f"Severity: {analysis['severity']['severity']}, "
                         f"Issues: {len(analysis['patterns'].get('error_types', []))}",
            })
        
        workflow_result["stages"]["analysis"] = analysis_results
        
        # Stage 3: Create tickets for significant issues
        if create_tickets:
            self._logger.info("Stage 3: Creating ServiceNow tickets")
            
            for service, analysis in analysis_results.items():
                severity = analysis.get("severity", {}).get("severity", "low")
                
                # Only create tickets for medium severity or higher
                if severity in ("critical", "high", "medium"):
                    formatted_logs = self.datadog_agent.format_logs(logs, service=service)
                    
                    ticket = self.servicenow_agent.create_ticket_from_analysis(
                        service_name=service,
                        analysis_report=analysis,
                        user_input=user_request,
                        log_context=formatted_logs,
                    )
                    
                    if "error" not in ticket:
                        workflow_result["tickets_created"].append({
                            "service": service,
                            "ticket_number": ticket.get("number"),
                            "priority": severity,
                        })
                        
                        self._agent_reports.append({
                            "agent": "ServiceNow Agent",
                            "action": f"Created ticket for {service}",
                            "result": f"Ticket: {ticket.get('number', 'N/A')}",
                        })
        
        # Generate summary
        workflow_result["summary"] = self._generate_workflow_summary(workflow_result)
        
        # Record orchestrator action
        self.record_action(
            action_type="full_workflow",
            description="Completed full analysis workflow",
            input_summary=user_request,
            output_summary=workflow_result["summary"],
        )
        
        return workflow_result
    
    def _generate_workflow_summary(self, workflow_result: dict) -> str:
        """Generate a natural language summary of the workflow."""
        stages = workflow_result.get("stages", {})
        tickets = workflow_result.get("tickets_created", [])
        
        lines = [
            "## AIOps Workflow Summary",
            "",
            f"**Time Range:** {workflow_result['time_range']['from']} to {workflow_result['time_range']['to']}",
            "",
        ]
        
        # DataDog summary
        dd_stage = stages.get("datadog", {})
        lines.append(f"### Log Collection")
        lines.append(f"- Logs retrieved: {dd_stage.get('logs_fetched', 0)}")
        lines.append(f"- Services affected: {', '.join(dd_stage.get('services_found', ['None']))}")
        lines.append("")
        
        # Analysis summary
        analysis = stages.get("analysis", {})
        if analysis:
            lines.append("### Analysis Results")
            for service, result in analysis.items():
                severity = result.get("severity", {}).get("severity", "unknown")
                error_count = len(result.get("patterns", {}).get("error_types", []))
                lines.append(f"- **{service}**: {severity.upper()} severity, {error_count} error types")
            lines.append("")
        
        # Tickets summary
        if tickets:
            lines.append("### Tickets Created")
            for ticket in tickets:
                lines.append(
                    f"- {ticket['ticket_number']}: [{ticket['priority'].upper()}] {ticket['service']}"
                )
        else:
            lines.append("### Tickets Created")
            lines.append("- No tickets created")
        
        return "\n".join(lines)
    
    def generate_report(self) -> str:
        """
        Generate a comprehensive report of all agent actions.
        
        Returns:
            Natural language report of all actions taken.
        """
        lines = [
            "# AIOps Multi-Agent Activity Report",
            "",
            f"**Orchestrator ID:** {self.agent_id}",
            f"**Total Actions:** {self._state.total_invocations}",
            "",
            "## Agent Actions",
            "",
        ]
        
        # Add reports from each agent
        for report in self._agent_reports:
            lines.append(f"### {report['agent']}")
            lines.append(f"- **Action:** {report['action']}")
            lines.append(f"- **Result:** {report['result']}")
            lines.append("")
        
        # Add orchestrator's own actions
        lines.append("## Orchestrator Actions")
        lines.append(self.get_action_summary())
        
        return "\n".join(lines)
    
    def get_all_agent_actions(self) -> list[dict]:
        """
        Get actions from all agents in the system.
        
        Returns:
            List of all agent actions with agent attribution.
        """
        all_actions = []
        
        # Orchestrator actions
        for action in self.action_history:
            all_actions.append({
                "agent": "Orchestrator",
                **action.model_dump(),
            })
        
        # DataDog agent actions
        if self._datadog_agent:
            for action in self._datadog_agent.action_history:
                all_actions.append({
                    "agent": "DataDog",
                    **action.model_dump(),
                })
        
        # Coding agent actions
        if self._coding_agent:
            for action in self._coding_agent.action_history:
                all_actions.append({
                    "agent": "Coding",
                    **action.model_dump(),
                })
        
        # ServiceNow agent actions
        if self._servicenow_agent:
            for action in self._servicenow_agent.action_history:
                all_actions.append({
                    "agent": "ServiceNow",
                    **action.model_dump(),
                })
        
        # Sort by timestamp
        all_actions.sort(key=lambda x: x.get("timestamp", ""))
        
        return all_actions
    
    def reset_all_agents(self) -> None:
        """Reset state for all agents."""
        self.reset_state()
        self._agent_reports = []
        
        if self._datadog_agent:
            self._datadog_agent.reset_state()
        if self._coding_agent:
            self._coding_agent.reset_state()
        if self._servicenow_agent:
            self._servicenow_agent.reset_state()
        
        self._logger.info("All agent states reset")
