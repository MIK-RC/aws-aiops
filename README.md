# AIOps Multi-Agent System

A production-ready multi-agent system for intelligent operations management using AWS Strands Agents SDK and Amazon Bedrock AgentCore.

## Overview

This system transforms traditional AIOps workflows into an intelligent multi-agent architecture where specialized agents collaborate to:

- **Fetch and analyze logs** from DataDog
- **Identify error patterns** and suggest code fixes
- **Create incident tickets** in ServiceNow
- **Generate comprehensive reports** for operations teams

## Features

- 🤖 **Multi-Agent Architecture**: Four specialized agents (Orchestrator, DataDog, Coding, ServiceNow) working together
- 🔄 **Swarm Coordination**: Autonomous agent collaboration using the Strands SDK Swarm pattern
- 💾 **Session Persistence**: S3-based memory for conversation continuity
- 📊 **Daily Cron Workflows**: Automated daily analysis with EventBridge scheduling
- 🚀 **Production Ready**: AgentCore deployment for serverless, scalable execution
- 🧪 **Modular Design**: Each agent can be used standalone or as part of the swarm

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    User / EventBridge                        │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Orchestrator Agent                         │
│  • Coordinates specialist agents                             │
│  • Maintains conversation memory                             │
│  • Generates final reports                                   │
└─────────────────────────────┬───────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│  DataDog Agent  │ │  Coding Agent   │ │ ServiceNow Agent│
│                 │ │                 │ │                 │
│ • Query logs    │ │ • Analyze errors│ │ • Create tickets│
│ • Extract       │ │ • Suggest fixes │ │ • Update status │
│   services      │ │ • Assess        │ │ • Track         │
│ • Format data   │ │   severity      │ │   incidents     │
└─────────────────┘ └─────────────────┘ └─────────────────┘
```

## Quick Start

### Prerequisites

- Python 3.12+
- AWS CLI configured with appropriate permissions
- Access to Amazon Bedrock (Claude models)
- DataDog API credentials
- ServiceNow instance credentials

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd aiops-multi-agent

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# For development
pip install -r requirements-dev.txt
```

### Configuration

1. **Set environment variables:**

```bash
export AWS_REGION=us-east-1
export DATADOG_API_KEY=your-api-key
export DATADOG_APP_KEY=your-app-key
export SERVICENOW_INSTANCE=your-instance.service-now.com
export SERVICENOW_USER=your-username
export SERVICENOW_PASS=your-password
```

2. **Or use a `.env` file:**

```env
AWS_REGION=us-east-1
DATADOG_API_KEY=your-api-key
DATADOG_APP_KEY=your-app-key
SERVICENOW_INSTANCE=your-instance.service-now.com
SERVICENOW_USER=your-username
SERVICENOW_PASS=your-password
```

3. **Customize configuration** in `config/` directory:
   - `settings.yaml`: Global settings, AWS region, session storage
   - `agents.yaml`: Agent prompts, model IDs, behavior
   - `tools.yaml`: Tool-specific settings (API endpoints, limits)

## Usage

### Command Line Interface

```bash
# Interactive chat with orchestrator
python -m src.main chat "Analyze errors in the payment service"

# Run daily analysis workflow
python -m src.main analyze --time-from now-1d --create-tickets

# Run multi-agent swarm
python -m src.main swarm "Investigate database connection issues"

# Test individual agents
python -m src.main test-agent datadog
python -m src.main test-agent coding
python -m src.main test-agent servicenow
```

### Programmatic Usage

#### Using Individual Agents (Standalone)

```python
from src.agents import DataDogAgent, CodingAgent, ServiceNowAgent

# DataDog Agent - standalone
datadog = DataDogAgent()
logs = datadog.fetch_logs(time_from="now-1h")
services = datadog.get_services(logs)

# Coding Agent - standalone
coding = CodingAgent()
analysis = coding.full_analysis(formatted_logs, "payment-service")
print(analysis["summary"])

# ServiceNow Agent - standalone
servicenow = ServiceNowAgent()
ticket = servicenow.create_ticket(
    title="Database connection timeout",
    description="Full details...",
    priority="high"
)
```

#### Using the Orchestrator

```python
from src.agents import OrchestratorAgent

# With session persistence
orchestrator = OrchestratorAgent(
    session_id="user-123",
    use_s3_storage=True,
    s3_bucket="my-sessions-bucket"
)

# Interactive conversation
response = orchestrator.invoke("What services had errors today?")

# Full analysis workflow
report = orchestrator.analyze_and_report(
    user_request="Analyze payment service issues",
    time_from="now-1d",
    create_tickets=True
)
```

#### Using the Swarm

```python
from src.workflows import AIOpsSwarm

swarm = AIOpsSwarm()
result = swarm.run("Analyze yesterday's errors and create tickets for critical issues")

print(f"Success: {result.success}")
print(f"Agents used: {result.agents_used}")
print(f"Summary: {result.summary}")
```

#### Running Daily Analysis

```python
from src.workflows import run_daily_analysis

result = run_daily_analysis(
    time_from="now-1d",
    time_to="now",
    create_tickets=True,
    dry_run=False
)

print(result["summary"])
```

## Deployment

### AgentCore Deployment (Recommended)

Deploy to Amazon Bedrock AgentCore for production:

```bash
# Build and push Docker image
./scripts/deploy.sh agentcore --region us-east-1

# The script will:
# 1. Create ECR repository
# 2. Build Docker image
# 3. Push to ECR
# 4. Output next steps for AgentCore configuration
```

### Lambda Deployment (for Cron Jobs)

```bash
# Deploy Lambda for scheduled execution
./scripts/deploy.sh lambda --region us-east-1

# Configure EventBridge rule for daily execution
aws events put-rule \
  --name aiops-daily-analysis \
  --schedule-expression "cron(0 6 * * ? *)" \
  --state ENABLED
```

## Project Structure

```
aiops-multi-agent/
├── config/                     # YAML configuration files
│   ├── settings.yaml           # Global settings
│   ├── agents.yaml             # Agent configurations
│   └── tools.yaml              # Tool configurations
│
├── src/                        # Source code
│   ├── agents/                 # Agent implementations
│   │   ├── base.py             # BaseAgent class
│   │   ├── orchestrator.py     # OrchestratorAgent
│   │   ├── datadog_agent.py    # DataDogAgent
│   │   ├── coding_agent.py     # CodingAgent
│   │   └── servicenow_agent.py # ServiceNowAgent
│   │
│   ├── tools/                  # Tool implementations
│   │   ├── datadog_tools.py    # DataDog API tools
│   │   ├── servicenow_tools.py # ServiceNow API tools
│   │   └── code_analysis_tools.py # Code analysis tools
│   │
│   ├── memory/                 # Session management
│   │   ├── session_manager.py  # Session factory
│   │   └── conversation_history.py
│   │
│   ├── workflows/              # Workflow orchestration
│   │   ├── swarm_coordinator.py # Multi-agent swarm
│   │   └── cron_workflow.py    # Daily analysis workflow
│   │
│   └── utils/                  # Utilities
│       ├── config_loader.py    # YAML config loading
│       └── logging_config.py   # Logging setup
│
├── deployment/                 # Deployment files
│   ├── agentcore/              # AgentCore deployment
│   └── lambda/                 # Lambda deployment
│
├── tests/                      # Test suite
│   ├── unit/                   # Unit tests
│   └── integration/            # Integration tests
│
└── scripts/                    # Utility scripts
    ├── deploy.sh               # Deployment script
    └── local_run.py            # Local testing
```

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/unit/test_agents.py -v

# Run integration tests
pytest tests/integration/ -v
```

## Configuration Reference

### settings.yaml

```yaml
aws:
  region: "us-east-1"

session:
  bucket: "aiops-agent-sessions"
  prefix: "sessions/"
  ttl: 604800  # 7 days

cron:
  default_time_from: "now-1d"
  default_time_to: "now"
  schedule: "cron(0 6 * * ? *)"

rate_limits:
  max_agent_iterations: 20
  max_handoffs: 15
  execution_timeout_seconds: 900
```

### agents.yaml

```yaml
orchestrator:
  name: "orchestrator_agent"
  model_id: "us.anthropic.claude-sonnet-4-20250514-v1:0"
  max_tokens: 4096
  system_prompt: |
    You are the AIOps Orchestrator Agent...

datadog:
  name: "datadog_agent"
  model_id: "us.anthropic.claude-3-5-haiku-20241022-v1:0"
  # ...
```

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| strands-agents | 1.19.0 | Core agent framework |
| boto3 | >=1.35.0 | AWS SDK |
| bedrock-agentcore | >=0.1.0 | AgentCore runtime |
| pydantic | >=2.4.0 | Data validation |
| PyYAML | >=6.0.1 | Configuration |
| requests | >=2.31.0 | HTTP client |

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `AWS_REGION` | No | AWS region (default: us-east-1) |
| `DATADOG_API_KEY` | Yes | DataDog API key |
| `DATADOG_APP_KEY` | Yes | DataDog Application key |
| `SERVICENOW_INSTANCE` | Yes | ServiceNow instance URL |
| `SERVICENOW_USER` | Yes | ServiceNow username |
| `SERVICENOW_PASS` | Yes | ServiceNow password |
| `AIOPS_CONFIG_DIR` | No | Config directory path |
| `AIOPS_SESSION_BACKEND` | No | Session backend (s3/file) |

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `pytest`
5. Submit a pull request

## License

MIT License - See LICENSE file for details.

## Support

For issues and questions:
- Open a GitHub issue
- Check the documentation in `docs/`
- Review the configuration examples in `config/`
