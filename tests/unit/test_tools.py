"""
Unit Tests for Tools Module

Tests for DataDog, ServiceNow, and Code Analysis tools.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.tools.datadog_tools import DataDogClient, query_logs, extract_unique_services, format_logs_for_analysis
from src.tools.servicenow_tools import ServiceNowClient, create_incident, update_incident, get_incident_status
from src.tools.code_analysis_tools import CodeAnalyzer, analyze_error_patterns, suggest_code_fix, assess_severity
from src.tools.s3_tools import S3Client, upload_service_report, upload_summary_report


class TestDataDogClient:
    """Tests for DataDogClient."""
    
    @pytest.fixture
    def client(self):
        """Create a DataDog client with mock credentials."""
        with patch.dict(os.environ, {
            "DATADOG_API_KEY": "test-api-key",
            "DATADOG_APP_KEY": "test-app-key",
        }):
            return DataDogClient(site="us5")
    
    def test_client_initialization(self, client):
        """Test client initializes with correct configuration."""
        assert client._api_key == "test-api-key"
        assert client._app_key == "test-app-key"
        assert client._site == "us5"
    
    def test_headers_property(self, client):
        """Test headers are correctly formatted."""
        headers = client.headers
        assert headers["DD-API-KEY"] == "test-api-key"
        assert headers["DD-APPLICATION-KEY"] == "test-app-key"
        assert headers["Content-Type"] == "application/json"
    
    @patch("src.tools.datadog_tools.requests.post")
    def test_query_logs_success(self, mock_post, client):
        """Test successful log query."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "data": [
                {"attributes": {"service": "test-service", "status": "error"}},
                {"attributes": {"service": "test-service", "status": "warn"}},
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response
        
        logs = client.query_logs(time_from="now-1h", time_to="now")
        
        assert len(logs) == 2
        mock_post.assert_called_once()
    
    @patch("src.tools.datadog_tools.requests.post")
    def test_query_logs_timeout(self, mock_post, client):
        """Test log query handles timeout."""
        import requests
        mock_post.side_effect = requests.exceptions.Timeout()
        
        logs = client.query_logs()
        
        assert logs == []
    
    def test_extract_services(self, client):
        """Test service extraction from logs."""
        logs = [
            {"attributes": {"service": "service-a"}},
            {"attributes": {"service": "service-b"}},
            {"attributes": {"service": "service-a"}},  # Duplicate
            {"attributes": {}},  # No service
        ]
        
        services = client.extract_services(logs)
        
        assert services == {"service-a", "service-b"}
    
    def test_format_logs(self, client):
        """Test log formatting."""
        logs = [
            {
                "attributes": {
                    "timestamp": "2024-01-15T10:30:00",
                    "status": "error",
                    "service": "test-service",
                    "message": "Test error message",
                }
            },
        ]
        
        formatted = client.format_logs(logs)
        
        assert "2024-01-15T10:30:00" in formatted
        assert "ERROR" in formatted
        assert "test-service" in formatted
        assert "Test error message" in formatted


class TestServiceNowClient:
    """Tests for ServiceNowClient."""
    
    @pytest.fixture
    def client(self):
        """Create a ServiceNow client with mock credentials."""
        with patch.dict(os.environ, {
            "SERVICENOW_INSTANCE": "test.service-now.com",
            "SERVICENOW_USER": "test-user",
            "SERVICENOW_PASS": "test-pass",
        }):
            return ServiceNowClient()
    
    def test_client_initialization(self, client):
        """Test client initializes with correct configuration."""
        assert client._instance == "test.service-now.com"
        assert client._username == "test-user"
        assert client._password == "test-pass"
    
    def test_base_url_property(self, client):
        """Test base URL is correctly formatted."""
        assert client.base_url == "https://test.service-now.com"
    
    @patch("src.tools.servicenow_tools.requests.post")
    def test_create_incident_success(self, mock_post, client):
        """Test successful incident creation."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "result": {
                "sys_id": "abc123",
                "number": "INC0012345",
            }
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response
        
        result = client.create_incident(
            short_description="Test incident",
            description="Test description",
        )
        
        assert result["sys_id"] == "abc123"
        assert result["number"] == "INC0012345"
    
    def test_priority_mapping(self, client):
        """Test priority to impact/urgency mapping."""
        impact, urgency = client._get_priority_values("critical")
        assert impact == "1"
        assert urgency == "1"
        
        impact, urgency = client._get_priority_values("low")
        assert impact == "3"
        assert urgency == "3"


class TestCodeAnalyzer:
    """Tests for CodeAnalyzer."""
    
    @pytest.fixture
    def analyzer(self):
        """Create a code analyzer."""
        return CodeAnalyzer()
    
    def test_analyze_patterns_identifies_errors(self, analyzer):
        """Test pattern analysis identifies error types."""
        log_context = """
        [2024-01-15T10:30:00] [ERROR] [payment-api] NullPointerException at line 42
        [2024-01-15T10:31:00] [ERROR] [payment-api] Connection refused to database
        [2024-01-15T10:32:00] [WARN] [payment-api] Timeout waiting for response
        """
        
        patterns = analyzer.analyze_patterns(log_context)
        
        assert "NullPointerException" in patterns["error_types"]
        assert "ConnectionRefused" in patterns["error_types"]
        assert "Timeout" in patterns["error_types"]
    
    def test_analyze_patterns_extracts_services(self, analyzer):
        """Test pattern analysis extracts services."""
        log_context = """
        [2024-01-15T10:30:00] [ERROR] [service-a] Error message
        [2024-01-15T10:31:00] [ERROR] [service-b] Error message
        """
        
        patterns = analyzer.analyze_patterns(log_context)
        
        assert "service-a" in patterns["affected_services"]
        assert "service-b" in patterns["affected_services"]
    
    def test_assess_severity_critical(self, analyzer):
        """Test severity assessment for critical errors."""
        patterns = {"error_types": ["OutOfMemoryError"]}
        
        severity = analyzer.assess_severity(patterns)
        
        assert severity == "critical"
    
    def test_assess_severity_high(self, analyzer):
        """Test severity assessment for high severity errors."""
        patterns = {"error_types": ["NullPointerException"]}
        
        severity = analyzer.assess_severity(patterns)
        
        assert severity == "high"
    
    def test_suggest_fixes(self, analyzer):
        """Test fix suggestions are generated."""
        patterns = {
            "error_types": ["NullPointerException", "ConnectionRefused"],
            "potential_causes": ["Network issues"],
        }
        
        suggestions = analyzer.suggest_fixes(patterns, "test-service")
        
        assert len(suggestions) >= 2
        assert any(s["error_type"] == "NullPointerException" for s in suggestions)
        assert any(s["error_type"] == "ConnectionRefused" for s in suggestions)


class TestS3Client:
    """Tests for S3Client."""
    
    @pytest.fixture
    def client(self):
        """Create an S3 client with mock credentials."""
        with patch.dict(os.environ, {
            "S3_REPORTS_BUCKET": "test-bucket",
            "AWS_DEFAULT_REGION": "us-east-1",
        }):
            with patch("src.tools.s3_tools.boto3.client"):
                return S3Client()
    
    def test_client_initialization(self, client):
        """Test client initializes with correct configuration."""
        assert client._bucket == "test-bucket"
    
    @patch("src.tools.s3_tools.boto3.client")
    def test_upload_report(self, mock_boto):
        """Test report upload."""
        with patch.dict(os.environ, {
            "S3_REPORTS_BUCKET": "test-bucket",
        }):
            mock_s3 = Mock()
            mock_boto.return_value = mock_s3
            
            client = S3Client()
            result = client.upload_report(
                service_name="test-service",
                content="# Test Report",
            )
            
            assert result["success"] is True
            assert "s3://" in result["s3_uri"]
            mock_s3.put_object.assert_called_once()


class TestToolFunctions:
    """Tests for tool functions (decorated with @tool)."""
    
    def test_query_logs_tool(self):
        """Test query_logs tool function has correct metadata."""
        # The tool decorator adds metadata
        assert hasattr(query_logs, "__name__")
        assert query_logs.__name__ == "query_logs"
    
    def test_create_incident_tool(self):
        """Test create_incident tool function has correct metadata."""
        assert hasattr(create_incident, "__name__")
        assert create_incident.__name__ == "create_incident"
    
    def test_analyze_error_patterns_tool(self):
        """Test analyze_error_patterns tool function has correct metadata."""
        assert hasattr(analyze_error_patterns, "__name__")
        assert analyze_error_patterns.__name__ == "analyze_error_patterns"
    
    def test_upload_service_report_tool(self):
        """Test upload_service_report tool function has correct metadata."""
        assert hasattr(upload_service_report, "__name__")
        assert upload_service_report.__name__ == "upload_service_report"
    
    def test_upload_summary_report_tool(self):
        """Test upload_summary_report tool function has correct metadata."""
        assert hasattr(upload_summary_report, "__name__")
        assert upload_summary_report.__name__ == "upload_summary_report"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
