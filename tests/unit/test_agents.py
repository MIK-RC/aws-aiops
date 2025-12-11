"""
Unit Tests for Agents Module

Tests for BaseAgent and individual agent classes.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.agents.base import BaseAgent, AgentAction, AgentState
from src.agents.datadog_agent import DataDogAgent
from src.agents.coding_agent import CodingAgent
from src.agents.servicenow_agent import ServiceNowAgent
from src.agents.orchestrator import OrchestratorAgent


class TestAgentAction:
    """Tests for AgentAction model."""
    
    def test_action_creation(self):
        """Test AgentAction creation with defaults."""
        action = AgentAction(
            action_type="test",
            description="Test action",
        )
        
        assert action.action_type == "test"
        assert action.description == "Test action"
        assert action.success is True
        assert action.error_message == ""
    
    def test_action_with_error(self):
        """Test AgentAction with error."""
        action = AgentAction(
            action_type="test",
            description="Failed action",
            success=False,
            error_message="Something went wrong",
        )
        
        assert action.success is False
        assert action.error_message == "Something went wrong"


class TestAgentState:
    """Tests for AgentState model."""
    
    def test_state_creation(self):
        """Test AgentState creation."""
        state = AgentState(
            agent_id="test-123",
            agent_name="test_agent",
        )
        
        assert state.agent_id == "test-123"
        assert state.agent_name == "test_agent"
        assert state.total_invocations == 0
        assert len(state.action_history) == 0


class TestBaseAgent:
    """Tests for BaseAgent functionality."""
    
    @pytest.fixture
    def mock_agent(self):
        """Create a mock concrete agent for testing."""
        # We need to create a concrete implementation since BaseAgent is abstract
        class TestAgent(BaseAgent):
            def get_tools(self):
                return []
        
        with patch("src.agents.base.Agent"):
            with patch("src.agents.base.BedrockModel"):
                agent = TestAgent(agent_type="test")
        
        return agent
    
    def test_agent_initialization(self, mock_agent):
        """Test agent initialization."""
        assert mock_agent._agent_type == "test"
        assert mock_agent.agent_name is not None
    
    def test_record_action(self, mock_agent):
        """Test action recording."""
        mock_agent.record_action(
            action_type="test",
            description="Test action",
            input_summary="input",
            output_summary="output",
        )
        
        assert len(mock_agent.action_history) == 1
        assert mock_agent.state.total_invocations == 1
        assert mock_agent.state.successful_invocations == 1
    
    def test_record_failed_action(self, mock_agent):
        """Test recording a failed action."""
        mock_agent.record_action(
            action_type="test",
            description="Failed action",
            success=False,
            error_message="Error",
        )
        
        assert mock_agent.state.failed_invocations == 1
    
    def test_get_action_summary(self, mock_agent):
        """Test action summary generation."""
        mock_agent.record_action(
            action_type="action1",
            description="First action",
        )
        mock_agent.record_action(
            action_type="action2",
            description="Second action",
        )
        
        summary = mock_agent.get_action_summary()
        
        assert "Action Summary" in summary
        assert "action1" in summary
        assert "action2" in summary
    
    def test_reset_state(self, mock_agent):
        """Test state reset."""
        mock_agent.record_action(action_type="test", description="Action")
        assert len(mock_agent.action_history) == 1
        
        mock_agent.reset_state()
        
        assert len(mock_agent.action_history) == 0
        assert mock_agent.state.total_invocations == 0


class TestDataDogAgent:
    """Tests for DataDogAgent."""
    
    @pytest.fixture
    def agent(self):
        """Create a DataDog agent with mocked dependencies."""
        with patch("src.agents.datadog_agent.DataDogClient"):
            with patch("src.agents.base.Agent"):
                with patch("src.agents.base.BedrockModel"):
                    agent = DataDogAgent()
        return agent
    
    def test_agent_has_correct_type(self, agent):
        """Test agent has correct type."""
        assert agent._agent_type == "datadog"
    
    def test_get_tools_returns_list(self, agent):
        """Test get_tools returns a list."""
        tools = agent.get_tools()
        assert isinstance(tools, list)
        assert len(tools) == 3  # query_logs, extract_unique_services, format_logs_for_analysis


class TestCodingAgent:
    """Tests for CodingAgent."""
    
    @pytest.fixture
    def agent(self):
        """Create a Coding agent with mocked dependencies."""
        with patch("src.agents.base.Agent"):
            with patch("src.agents.base.BedrockModel"):
                agent = CodingAgent()
        return agent
    
    def test_agent_has_correct_type(self, agent):
        """Test agent has correct type."""
        assert agent._agent_type == "coding"
    
    def test_get_tools_returns_list(self, agent):
        """Test get_tools returns a list."""
        tools = agent.get_tools()
        assert isinstance(tools, list)
        assert len(tools) == 3  # analyze_error_patterns, suggest_code_fix, assess_severity
    
    def test_full_analysis_method(self, agent):
        """Test full_analysis method."""
        sample_logs = """
        [2024-01-15T10:30:00] [ERROR] [test-service] NullPointerException
        """
        
        result = agent.full_analysis(sample_logs, "test-service")
        
        assert "service" in result
        assert "patterns" in result
        assert "severity" in result
        assert "suggestions" in result


class TestServiceNowAgent:
    """Tests for ServiceNowAgent."""
    
    @pytest.fixture
    def agent(self):
        """Create a ServiceNow agent with mocked dependencies."""
        with patch("src.agents.servicenow_agent.ServiceNowClient"):
            with patch("src.agents.base.Agent"):
                with patch("src.agents.base.BedrockModel"):
                    agent = ServiceNowAgent()
        return agent
    
    def test_agent_has_correct_type(self, agent):
        """Test agent has correct type."""
        assert agent._agent_type == "servicenow"
    
    def test_get_tools_returns_list(self, agent):
        """Test get_tools returns a list."""
        tools = agent.get_tools()
        assert isinstance(tools, list)
        assert len(tools) == 3  # create_incident, update_incident, get_incident_status


class TestOrchestratorAgent:
    """Tests for OrchestratorAgent."""
    
    @pytest.fixture
    def agent(self):
        """Create an Orchestrator agent with mocked dependencies."""
        with patch("src.agents.base.Agent"):
            with patch("src.agents.base.BedrockModel"):
                agent = OrchestratorAgent()
        return agent
    
    def test_agent_has_correct_type(self, agent):
        """Test agent has correct type."""
        assert agent._agent_type == "orchestrator"
    
    def test_specialist_agents_lazy_loading(self, agent):
        """Test specialist agents are lazily loaded."""
        assert agent._datadog_agent is None
        assert agent._coding_agent is None
        assert agent._servicenow_agent is None
    
    def test_generate_report(self, agent):
        """Test report generation."""
        agent.record_action(
            action_type="test",
            description="Test action",
        )
        
        report = agent.generate_report()
        
        assert "Activity Report" in report
        assert "Orchestrator" in report


class TestStandaloneUsage:
    """Tests to verify agents can be used standalone."""
    
    def test_datadog_agent_standalone(self):
        """Test DataDog agent can be instantiated standalone."""
        with patch("src.agents.datadog_agent.DataDogClient"):
            with patch("src.agents.base.Agent"):
                with patch("src.agents.base.BedrockModel"):
                    agent = DataDogAgent()
                    
                    # Agent should be fully functional
                    assert agent.agent_name is not None
                    assert agent.agent_id is not None
                    assert callable(agent.invoke)
    
    def test_coding_agent_standalone(self):
        """Test Coding agent can be instantiated standalone."""
        with patch("src.agents.base.Agent"):
            with patch("src.agents.base.BedrockModel"):
                agent = CodingAgent()
                
                # Agent should be fully functional
                assert agent.agent_name is not None
                assert hasattr(agent, "analyze_logs")
                assert hasattr(agent, "get_fix_suggestions")
    
    def test_servicenow_agent_standalone(self):
        """Test ServiceNow agent can be instantiated standalone."""
        with patch("src.agents.servicenow_agent.ServiceNowClient"):
            with patch("src.agents.base.Agent"):
                with patch("src.agents.base.BedrockModel"):
                    agent = ServiceNowAgent()
                    
                    # Agent should be fully functional
                    assert agent.agent_name is not None
                    assert hasattr(agent, "create_ticket")
                    assert hasattr(agent, "update_ticket")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
