"""
Swarm Coordinator Module

Implements multi-agent coordination using the Strands SDK Swarm pattern.
Enables autonomous collaboration between DataDog, Coding, and ServiceNow agents.
"""

# from strands import Agent
from strands.multiagent import Swarm

from ..agents import CodingAgent, DataDogAgent, ServiceNowAgent  # , OrchestratorAgent
from ..utils.config_loader import get_config
from ..utils.logging_config import get_logger

logger = get_logger("workflows.swarm")


class AIOpsSwarm:
    """
    Multi-Agent Swarm for AIOps operations.

    Coordinates multiple specialist agents using the Strands SDK Swarm pattern,
    enabling autonomous agent collaboration with shared context and handoffs.

    The swarm includes:
    - DataDog Agent: Fetches and formats logs
    - Coding Agent: Analyzes errors and suggests fixes
    - ServiceNow Agent: Creates incident tickets

    Usage:
        # Create swarm
        swarm = AIOpsSwarm()

        # Run a task
        result = swarm.run("Analyze yesterday's errors and create tickets for critical issues")

        # Get summary
        print(result.summary)
    """

    def __init__(
        self,
        model_id: str | None = None,
        region: str | None = None,
        max_handoffs: int = 15,
        max_iterations: int = 20,
        execution_timeout: float = 900.0,
        node_timeout: float = 300.0,
    ):
        """
        Initialize the AIOps Swarm.

        Args:
            model_id: Optional Bedrock model ID for all agents.
            region: Optional AWS region override.
            max_handoffs: Maximum agent handoffs allowed.
            max_iterations: Maximum total iterations.
            execution_timeout: Total execution timeout in seconds.
            node_timeout: Individual agent timeout in seconds.
        """
        config = get_config()
        rate_limits = config.settings.rate_limits

        self._max_handoffs = max_handoffs or rate_limits.max_handoffs
        self._max_iterations = max_iterations or rate_limits.max_agent_iterations
        self._execution_timeout = execution_timeout or rate_limits.execution_timeout_seconds
        self._node_timeout = node_timeout or rate_limits.node_timeout_seconds

        # Initialize agents
        self._datadog_agent = DataDogAgent(model_id=model_id, region=region)
        self._coding_agent = CodingAgent(model_id=model_id, region=region)
        self._servicenow_agent = ServiceNowAgent(model_id=model_id, region=region)

        # Create the swarm
        self._swarm = self._create_swarm()

        logger.info(
            f"Initialized AIOps Swarm with {self._max_handoffs} max handoffs, "
            f"{self._execution_timeout}s timeout"
        )

    def _create_swarm(self) -> Swarm:
        """Create the Strands Swarm with our agents."""
        # Get the inner Strands Agent instances
        agents = [
            self._datadog_agent.inner_agent,
            self._coding_agent.inner_agent,
            self._servicenow_agent.inner_agent,
        ]

        # Create swarm with configuration
        return Swarm(
            nodes=agents,
            max_handoffs=self._max_handoffs,
            max_iterations=self._max_iterations,
            execution_timeout=self._execution_timeout,
            node_timeout=self._node_timeout,
        )

    @property
    def datadog_agent(self) -> DataDogAgent:
        """Get the DataDog agent."""
        return self._datadog_agent

    @property
    def coding_agent(self) -> CodingAgent:
        """Get the Coding agent."""
        return self._coding_agent

    @property
    def servicenow_agent(self) -> ServiceNowAgent:
        """Get the ServiceNow agent."""
        return self._servicenow_agent

    def run(
        self,
        task: str,
        start_agent: str | None = None,
    ) -> "SwarmResult":
        """
        Run a task through the swarm.

        The swarm will automatically coordinate agents to complete the task,
        with agents handing off to each other as needed.

        Args:
            task: The task description for the swarm.
            start_agent: Optional name of agent to start with.
                        Defaults to datadog_agent for log-related tasks.

        Returns:
            SwarmResult containing execution details and output.
        """
        logger.info(f"Starting swarm task: {task[:100]}...")

        # Determine starting agent
        if start_agent is None:
            # Default to DataDog for log analysis tasks
            if any(word in task.lower() for word in ["log", "error", "analyze", "fetch"]):
                start_agent = self._datadog_agent.agent_name
            else:
                start_agent = self._datadog_agent.agent_name

        try:
            # Execute the swarm
            result = self._swarm(
                task,
                start=start_agent,
            )

            logger.info("Swarm task completed successfully")

            return SwarmResult(
                success=True,
                task=task,
                output=str(result),
                agents_used=self._get_agents_used(),
                summary=self._generate_summary(),
            )

        except Exception as e:
            logger.error(f"Swarm task failed: {e}")

            return SwarmResult(
                success=False,
                task=task,
                output="",
                error=str(e),
                agents_used=self._get_agents_used(),
                summary=f"Task failed: {e}",
            )

    async def run_async(
        self,
        task: str,
        start_agent: str | None = None,
    ) -> "SwarmResult":
        """
        Asynchronously run a task through the swarm.

        Args:
            task: The task description for the swarm.
            start_agent: Optional name of agent to start with.

        Returns:
            SwarmResult containing execution details and output.
        """
        logger.info(f"Starting async swarm task: {task[:100]}...")

        if start_agent is None:
            start_agent = self._datadog_agent.agent_name

        try:
            # Execute the swarm asynchronously
            result = self._swarm.stream_async(
                task,
                start=start_agent,
            )

            output = ""
            async for event in result:
                if hasattr(event, "data"):
                    output += str(event.get("data"))

            logger.info("Async swarm task completed successfully")

            return SwarmResult(
                success=True,
                task=task,
                output=output,
                agents_used=self._get_agents_used(),
                summary=self._generate_summary(),
            )

        except Exception as e:
            logger.error(f"Async swarm task failed: {e}")

            return SwarmResult(
                success=False,
                task=task,
                output="",
                error=str(e),
                agents_used=self._get_agents_used(),
                summary=f"Task failed: {e}",
            )

    def _get_agents_used(self) -> list[str]:
        """Get list of agents that performed actions."""
        agents = []

        if self._datadog_agent.state.total_invocations > 0:
            agents.append("DataDog Agent")
        if self._coding_agent.state.total_invocations > 0:
            agents.append("Coding Agent")
        if self._servicenow_agent.state.total_invocations > 0:
            agents.append("ServiceNow Agent")

        return agents

    def _generate_summary(self) -> str:
        """Generate a summary of the swarm execution."""
        lines = [
            "## AIOps Swarm Execution Summary",
            "",
        ]

        # DataDog summary
        dd_state = self._datadog_agent.state
        if dd_state.total_invocations > 0:
            lines.append("### DataDog Agent")
            lines.append(f"- Actions: {dd_state.total_invocations}")
            lines.append(f"- Successful: {dd_state.successful_invocations}")
            lines.append("")

        # Coding summary
        code_state = self._coding_agent.state
        if code_state.total_invocations > 0:
            lines.append("### Coding Agent")
            lines.append(f"- Actions: {code_state.total_invocations}")
            lines.append(f"- Successful: {code_state.successful_invocations}")
            lines.append("")

        # ServiceNow summary
        sn_state = self._servicenow_agent.state
        if sn_state.total_invocations > 0:
            lines.append("### ServiceNow Agent")
            lines.append(f"- Actions: {sn_state.total_invocations}")
            lines.append(f"- Successful: {sn_state.successful_invocations}")
            lines.append("")

        return "\n".join(lines)

    def get_all_actions(self) -> list[dict]:
        """Get all actions from all agents."""
        actions = []

        for action in self._datadog_agent.action_history:
            actions.append({"agent": "DataDog", **action.model_dump()})

        for action in self._coding_agent.action_history:
            actions.append({"agent": "Coding", **action.model_dump()})

        for action in self._servicenow_agent.action_history:
            actions.append({"agent": "ServiceNow", **action.model_dump()})

        actions.sort(key=lambda x: x.get("timestamp", ""))
        return actions

    def reset(self) -> None:
        """Reset all agent states."""
        self._datadog_agent.reset_state()
        self._coding_agent.reset_state()
        self._servicenow_agent.reset_state()
        logger.info("Swarm agents reset")


class SwarmResult:
    """
    Result from a swarm execution.

    Contains the task output, execution metadata, and summary.
    """

    def __init__(
        self,
        success: bool,
        task: str,
        output: str,
        agents_used: list[str],
        summary: str,
        error: str = "",
    ):
        self.success = success
        self.task = task
        self.output = output
        self.agents_used = agents_used
        self.summary = summary
        self.error = error

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "task": self.task,
            "output": self.output,
            "agents_used": self.agents_used,
            "summary": self.summary,
            "error": self.error,
        }

    def __str__(self) -> str:
        """String representation."""
        if self.success:
            return f"SwarmResult(success=True, agents={self.agents_used})"
        return f"SwarmResult(success=False, error={self.error})"
