"""
Tools Module

Custom tools for the AIOps Multi-Agent System.
Each tool is implemented using the @tool decorator from Strands Agents SDK.
"""

from .code_analysis_tools import (
    analyze_error_patterns,
    assess_severity,
    suggest_code_fix,
)
from .datadog_tools import (
    DataDogClient,
    extract_unique_services,
    format_logs_for_analysis,
    query_logs,
)
from .servicenow_tools import (
    ServiceNowClient,
    create_incident,
    get_incident_status,
    update_incident,
)

__all__ = [
    # DataDog tools
    "query_logs",
    "extract_unique_services",
    "format_logs_for_analysis",
    "DataDogClient",
    # ServiceNow tools
    "create_incident",
    "update_incident",
    "get_incident_status",
    "ServiceNowClient",
    # Code analysis tools
    "analyze_error_patterns",
    "suggest_code_fix",
    "assess_severity",
]
