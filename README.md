# AIOps Proactive Workflow

A multi-agent system for proactive operations management. Automatically analyzes services with issues, creates incident tickets, and stores reports to S3.

## Overview

This system runs as an ECS container triggered by AWS EventBridge. When triggered, it:

1. Fetches services with errors/warnings from DataDog
2. Processes each service in parallel
3. Analyzes errors and suggests fixes
4. Creates ServiceNow tickets for significant issues
5. Uploads individual reports to S3
6. Generates a summary report

## Architecture

```
EventBridge (scheduled)
        │
        ▼
Bedrock Agent Runtime API
        │
        ▼
┌──────────────────────────────────────────────────────────────┐
│  AgentCore Runtime (managed by AWS)                           │
│                                                               │
│  ┌─────────────┐                                             │
│  │  main.py    │                                             │
│  └──────┬──────┘                                             │
│         │                                                     │
│         ▼                                                     │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  ProactiveWorkflow                                       │ │
│  │                                                          │ │
│  │  1. DataDog Agent → Fetch services with issues           │ │
│  │                                                          │ │
│  │  2. ThreadPoolExecutor (50 workers)                      │ │
│  │     ┌────────────────────────────────────────────────┐   │ │
│  │     │  Per Service → AIOpsSwarm:                     │   │ │
│  │     │  • Coding Agent → Analyze errors               │   │ │
│  │     │  • ServiceNow Agent → Create ticket            │   │ │
│  │     │  • S3 Agent → Upload report                    │   │ │
│  │     │  (Agents coordinate via Swarm handoffs)        │   │ │
│  │     └────────────────────────────────────────────────┘   │ │
│  │                                                          │ │
│  │  3. S3 Agent → Upload summary                            │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                               │
└──────────────────────────────────────────────────────────────┘
        │
        ▼
┌──────────────────┐
│  S3 Bucket       │
│  ├── {service}/  │
│  │   └── {ts}.md │
│  └── summaries/  │
│      └── {date}/ │
│          └── .md │
└──────────────────┘
```

The workflow uses **Swarm** for agent coordination within each service, enabling:
- LLM-driven agent handoffs
- Easy addition of new agents (e.g., Remediation Agent)
- Autonomous decision-making per service

## Agents

| Agent | Responsibility |
|-------|----------------|
| DataDog Agent | Fetch error/warning logs, identify affected services |
| Coding Agent | Analyze errors, identify root causes, suggest fixes |
| ServiceNow Agent | Create incident tickets for medium+ severity issues |
| S3 Agent | Upload service reports and summary to S3 |

## Quick Start

### Prerequisites

- Python 3.12+
- AWS account with Bedrock access
- DataDog API credentials
- ServiceNow instance credentials
- S3 bucket for reports

### Installation

```bash
# Clone and setup
git clone <repository-url>
cd aiops-proactive-workflow
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your credentials
```

### Configuration

Edit `.env`:

```env
# AWS
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_DEFAULT_REGION=us-east-1

# DataDog
DATADOG_API_KEY=your-api-key
DATADOG_APP_KEY=your-app-key
DATADOG_SITE=us5

# ServiceNow
SERVICENOW_INSTANCE=your-instance.service-now.com
SERVICENOW_USER=your-username
SERVICENOW_PASS=your-password

# S3 Reports
S3_REPORTS_BUCKET=your-reports-bucket
```

### Run Locally

```bash
python -m src.main
```

### Run with Docker

```bash
docker build -t aiops-proactive .
docker run --env-file .env aiops-proactive
```

## S3 Report Structure

```
s3://your-reports-bucket/
├── payment-service/
│   ├── 2024-12-16T10-30-00Z.md
│   └── 2024-12-17T10-30-00Z.md
├── auth-service/
│   └── 2024-12-16T10-30-00Z.md
└── summaries/
    └── 2024-12-16/
        └── 2024-12-16T10-35-00Z.md
```

## Report Format

Each service report follows this format:

```markdown
# Error Report: payment-service

Generated: 2024-12-16 10:30:00 UTC

## Summary
- Severity: HIGH
- Error types: 3
- Recurring issues: 2
- ServiceNow ticket: INC0012345

## Errors Detected
- ConnectionRefused
- Timeout
- DatabaseError

## Root Cause Analysis
- Network connectivity issues or service unavailability
- Database connection pool exhaustion or query issues

## Suggested Fixes
### 1. ConnectionRefused
**Issue:** Service connection failure
**Fix:** Implement retry logic with exponential backoff
**Prevention:** Use connection pools and health checks

## Related Logs
```
[2024-12-16T10:25:00] [ERROR] [payment-service] Connection refused...
```
```

## Configuration

### Workflow Settings (config/settings.yaml)

```yaml
workflow:
  default_time_from: "now-1d"
  default_time_to: "now"
  max_workers: 50
  use_lightweight_processor: false  # true = Option A, false = Option B
```

### Processing Modes

| Mode | Setting | Description |
|------|---------|-------------|
| Option A | `use_lightweight_processor: true` | Direct agent calls, faster, less overhead |
| Option B | `use_lightweight_processor: false` | Full orchestrator per service, more reasoning |

## Project Structure

```
aiops-proactive-workflow/
├── config/
│   ├── settings.yaml      # Workflow and global settings
│   ├── agents.yaml        # Agent configurations
│   └── tools.yaml         # Tool configurations
├── src/
│   ├── agents/
│   │   ├── base.py        # BaseAgent class
│   │   ├── datadog_agent.py
│   │   ├── coding_agent.py
│   │   ├── servicenow_agent.py
│   │   ├── s3_agent.py
│   │   └── orchestrator.py
│   ├── tools/
│   │   ├── datadog_tools.py
│   │   ├── code_analysis_tools.py
│   │   ├── servicenow_tools.py
│   │   └── s3_tools.py
│   ├── workflows/
│   │   ├── swarm_coordinator.py  # AIOpsSwarm for agent coordination
│   │   └── proactive_workflow.py # Main workflow with parallel processing
│   ├── utils/
│   │   ├── config_loader.py
│   │   └── logging_config.py
│   └── main.py            # Entry point
├── tests/
├── Dockerfile
├── requirements.txt
└── .env.example
```

## AWS Deployment

### AgentCore Deployment

1. Build and push Docker image to ECR:
```bash
docker build -t aiops-proactive .
docker tag aiops-proactive:latest <account>.dkr.ecr.<region>.amazonaws.com/aiops-proactive:latest
docker push <account>.dkr.ecr.<region>.amazonaws.com/aiops-proactive:latest
```

2. Configure AgentCore with the image URI

3. Create EventBridge rule to trigger the agent on schedule:
```
Schedule: rate(1 day) or cron(0 6 * * ? *)
Target: Bedrock Agent Runtime API
```

**Flow:**
```
EventBridge (schedule) → Bedrock Agent Runtime API → AgentCore → Proactive Workflow
```

### IAM Permissions

The AgentCore execution role needs:
- `bedrock:InvokeModel` for Bedrock LLM calls
- `s3:PutObject` for report uploads
- `logs:*` for CloudWatch

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| AWS_ACCESS_KEY_ID | Yes | AWS credentials |
| AWS_SECRET_ACCESS_KEY | Yes | AWS credentials |
| AWS_DEFAULT_REGION | No | Default: us-east-1 |
| DATADOG_API_KEY | Yes | DataDog API key |
| DATADOG_APP_KEY | Yes | DataDog App key |
| DATADOG_SITE | No | Default: us5 |
| SERVICENOW_INSTANCE | Yes | ServiceNow URL |
| SERVICENOW_USER | Yes | ServiceNow username |
| SERVICENOW_PASS | Yes | ServiceNow password |
| S3_REPORTS_BUCKET | Yes | S3 bucket for reports |

## Testing

```bash
pytest tests/ -v
```

## License

MIT License
