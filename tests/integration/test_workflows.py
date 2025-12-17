"""
Integration Tests for Workflows Module

Tests for workflow coordination, including swarm and proactive workflows.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.workflows.swarm_coordinator import AIOpsSwarm, SwarmResult


class TestSwarmResult:
    """Tests for SwarmResult."""
    
    def test_successful_result(self):
        """Test successful SwarmResult."""
        result = SwarmResult(
            success=True,
            task="Test task",
            output="Test output",
            agents_used=["DataDog Agent", "Coding Agent"],
            summary="Test summary",
        )
        
        assert result.success is True
        assert result.task == "Test task"
        assert len(result.agents_used) == 2
    
    def test_failed_result(self):
        """Test failed SwarmResult."""
        result = SwarmResult(
            success=False,
            task="Test task",
            output="",
            agents_used=[],
            summary="Failed",
            error="Test error",
        )
        
        assert result.success is False
        assert result.error == "Test error"
    
    def test_to_dict(self):
        """Test SwarmResult to_dict conversion."""
        result = SwarmResult(
            success=True,
            task="Test",
            output="Output",
            agents_used=["Agent1"],
            summary="Summary",
        )
        
        result_dict = result.to_dict()
        
        assert result_dict["success"] is True
        assert result_dict["task"] == "Test"


class TestAIOpsSwarm:
    """Tests for AIOpsSwarm."""
    
    @pytest.fixture
    def swarm(self):
        """Create a swarm with mocked agents."""
        with patch("src.workflows.swarm_coordinator.DataDogAgent"):
            with patch("src.workflows.swarm_coordinator.CodingAgent"):
                with patch("src.workflows.swarm_coordinator.ServiceNowAgent"):
                    with patch("src.workflows.swarm_coordinator.S3Agent"):
                        with patch("src.workflows.swarm_coordinator.Swarm"):
                            swarm = AIOpsSwarm()
        return swarm
    
    def test_swarm_initialization(self, swarm):
        """Test swarm initializes correctly."""
        assert swarm._coding_agent is not None
        assert swarm._servicenow_agent is not None
    
    def test_get_agents_used_empty(self, swarm):
        """Test getting agents used when none have actions."""
        # Mock the agents with zero invocations
        for agent in [swarm._coding_agent, swarm._servicenow_agent]:
            if agent:
                agent.state = Mock()
                agent.state.total_invocations = 0
        
        if swarm._datadog_agent:
            swarm._datadog_agent.state = Mock()
            swarm._datadog_agent.state.total_invocations = 0
        
        if swarm._s3_agent:
            swarm._s3_agent.state = Mock()
            swarm._s3_agent.state.total_invocations = 0
        
        agents = swarm._get_agents_used()
        assert agents == []
    
    def test_reset_clears_all_agents(self, swarm):
        """Test reset clears all agent states."""
        swarm.reset()
        # Should not raise any errors


class TestProactiveWorkflow:
    """Tests for ProactiveWorkflow."""
    
    @pytest.fixture
    def workflow(self):
        """Create a workflow with mocked dependencies."""
        with patch("src.workflows.proactive_workflow.DataDogAgent") as mock_dd:
            with patch("src.workflows.proactive_workflow.S3Agent") as mock_s3:
                with patch("src.workflows.proactive_workflow.AIOpsSwarm"):
                    # Setup mock DataDog agent
                    mock_dd_instance = Mock()
                    mock_dd_instance._client = Mock()
                    mock_dd_instance._client.query_logs.return_value = []
                    mock_dd_instance._client.extract_services.return_value = set()
                    mock_dd.return_value = mock_dd_instance
                    
                    # Setup mock S3 agent
                    mock_s3_instance = Mock()
                    mock_s3.return_value = mock_s3_instance
                    
                    from src.workflows.proactive_workflow import ProactiveWorkflow
                    workflow = ProactiveWorkflow()
        return workflow
    
    def test_workflow_initialization(self, workflow):
        """Test workflow initializes with correct defaults."""
        assert workflow._time_from is not None
        assert workflow._time_to is not None
        assert workflow._max_workers > 0


class TestWorkflowIntegration:
    """Integration tests for complete workflows."""
    
    def test_swarm_with_mock_task(self):
        """Test swarm execution with a mock task."""
        with patch("src.workflows.swarm_coordinator.DataDogAgent") as mock_dd:
            with patch("src.workflows.swarm_coordinator.CodingAgent") as mock_code:
                with patch("src.workflows.swarm_coordinator.ServiceNowAgent") as mock_sn:
                    with patch("src.workflows.swarm_coordinator.S3Agent") as mock_s3:
                        with patch("src.workflows.swarm_coordinator.Swarm") as mock_swarm:
                            # Setup mock agents with proper state
                            for mock_agent_class in [mock_dd, mock_code, mock_sn, mock_s3]:
                                mock_instance = Mock()
                                mock_instance.state = Mock()
                                mock_instance.state.total_invocations = 0
                                mock_instance.reset_state = Mock()
                                mock_agent_class.return_value = mock_instance
                            
                            # Setup mock swarm
                            mock_swarm_instance = Mock()
                            mock_swarm_instance.run.return_value = Mock(
                                output="Test output",
                                agent=Mock(agent_name="test_agent")
                            )
                            mock_swarm.return_value = mock_swarm_instance
                            
                            swarm = AIOpsSwarm()
                            result = swarm.run("Test task")
                            
                            assert result.task == "Test task"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
