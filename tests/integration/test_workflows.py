"""
Integration Tests for Workflows Module

Tests for workflow coordination, including swarm and cron workflows.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.workflows.swarm_coordinator import AIOpsSwarm, SwarmResult
from src.workflows.cron_workflow import DailyAnalysisWorkflow, run_daily_analysis


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
                    with patch("src.workflows.swarm_coordinator.Swarm"):
                        swarm = AIOpsSwarm()
        return swarm
    
    def test_swarm_initialization(self, swarm):
        """Test swarm initializes correctly."""
        assert swarm._datadog_agent is not None
        assert swarm._coding_agent is not None
        assert swarm._servicenow_agent is not None
    
    def test_get_agents_used_empty(self, swarm):
        """Test getting agents used when none have actions."""
        # Need to mock the state properly
        swarm._datadog_agent.state = Mock()
        swarm._datadog_agent.state.total_invocations = 0
        swarm._coding_agent.state = Mock()
        swarm._coding_agent.state.total_invocations = 0
        swarm._servicenow_agent.state = Mock()
        swarm._servicenow_agent.state.total_invocations = 0
        
        agents = swarm._get_agents_used()
        assert agents == []
    
    def test_reset_clears_all_agents(self, swarm):
        """Test reset clears all agent states."""
        swarm.reset()
        # Should not raise any errors


class TestDailyAnalysisWorkflow:
    """Tests for DailyAnalysisWorkflow."""
    
    @pytest.fixture
    def workflow(self):
        """Create a workflow with mocked agents."""
        with patch("src.workflows.cron_workflow.DataDogAgent") as mock_dd:
            with patch("src.workflows.cron_workflow.CodingAgent") as mock_code:
                with patch("src.workflows.cron_workflow.ServiceNowAgent") as mock_sn:
                    # Setup mock returns
                    mock_dd_instance = Mock()
                    mock_dd_instance.fetch_logs.return_value = []
                    mock_dd_instance.get_services.return_value = []
                    mock_dd.return_value = mock_dd_instance
                    
                    workflow = DailyAnalysisWorkflow(dry_run=True)
        return workflow
    
    def test_workflow_initialization(self, workflow):
        """Test workflow initializes with correct defaults."""
        assert workflow._time_from == "now-1d"
        assert workflow._time_to == "now"
        assert workflow._dry_run is True
    
    def test_empty_logs_report(self, workflow):
        """Test workflow handles empty logs correctly."""
        result = workflow.execute()
        
        assert result["success"] is True
        assert result["logs"]["total_fetched"] == 0
    
    def test_execute_for_lambda_returns_proper_format(self, workflow):
        """Test execute_for_lambda returns Lambda-compatible response."""
        response = workflow.execute_for_lambda()
        
        assert "statusCode" in response
        assert "body" in response
        assert "headers" in response
    
    def test_build_empty_report(self, workflow):
        """Test building empty report."""
        report = workflow._build_empty_report("Test reason")
        
        assert report["success"] is True
        assert report["summary"] == "Test reason"


class TestRunDailyAnalysis:
    """Tests for run_daily_analysis convenience function."""
    
    def test_function_creates_workflow(self):
        """Test function creates and executes workflow."""
        with patch("src.workflows.cron_workflow.DailyAnalysisWorkflow") as mock_workflow:
            mock_instance = Mock()
            mock_instance.execute.return_value = {"success": True}
            mock_workflow.return_value = mock_instance
            
            result = run_daily_analysis(dry_run=True)
            
            mock_workflow.assert_called_once()
            mock_instance.execute.assert_called_once()


class TestWorkflowIntegration:
    """Integration tests for complete workflows."""
    
    def test_workflow_with_mock_data(self):
        """Test complete workflow with mock data."""
        with patch("src.workflows.cron_workflow.DataDogAgent") as mock_dd:
            with patch("src.workflows.cron_workflow.CodingAgent") as mock_code:
                with patch("src.workflows.cron_workflow.ServiceNowAgent") as mock_sn:
                    # Setup mock DataDog agent
                    mock_dd_instance = Mock()
                    mock_dd_instance.fetch_logs.return_value = [
                        {"attributes": {"service": "test-service", "status": "error"}}
                    ]
                    mock_dd_instance.get_services.return_value = ["test-service"]
                    mock_dd_instance.format_logs.return_value = "[ERROR] test message"
                    mock_dd.return_value = mock_dd_instance
                    
                    # Setup mock Coding agent
                    mock_code_instance = Mock()
                    mock_code_instance.full_analysis.return_value = {
                        "severity": {"severity": "medium"},
                        "patterns": {"error_types": ["TestError"]},
                        "suggestions": [],
                        "summary": "Test summary",
                    }
                    mock_code.return_value = mock_code_instance
                    
                    # Setup mock ServiceNow agent
                    mock_sn_instance = Mock()
                    mock_sn_instance.create_ticket_from_analysis.return_value = {
                        "number": "INC0012345",
                        "sys_id": "abc123",
                    }
                    mock_sn.return_value = mock_sn_instance
                    
                    # Run workflow
                    workflow = DailyAnalysisWorkflow(dry_run=False)
                    result = workflow.execute()
                    
                    # Verify results
                    assert result["success"] is True
                    assert result["logs"]["total_fetched"] == 1
                    assert "test-service" in result["logs"]["services_found"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
