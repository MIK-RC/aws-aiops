"""
Tools Module

Custom tools for the AIOps Multi-Agent System.
Each tool is implemented using the @tool decorator from Strands Agents SDK.
"""

from .datadog_tools import (
    query_logs,
    extract_unique_services,
    format_logs_for_analysis,
    DataDogClient,
)
from .servicenow_tools import (
    create_incident,
    update_incident,
    get_incident_status,
    ServiceNowClient,
)
from .code_analysis_tools import (
    analyze_error_patterns,
    suggest_code_fix,
    assess_severity,
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
