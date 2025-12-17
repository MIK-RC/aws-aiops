# AIOps Proactive Workflow

A multi-agent system for proactive operations management. Automatically analyzes services with issues, creates incident tickets, and stores reports to S3.

## Overview

This system runs on AWS Bedrock AgentCore, triggered by EventBridge. When triggered, it:

1. Fetches services with errors/warnings from DataDog
2. Processes each service in parallel (up to 50 workers)
3. Analyzes errors and suggests fixes using AI
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

## Local Development

### Option 1: Run Workflow Directly

```bash
# Run the proactive workflow
./scripts/run_local.sh direct

# Or without the script
python -m src.main --mode proactive
```

### Option 2: Start Local Server

```bash
# Start AgentCore server on port 8080
./scripts/run_local.sh server

# Then invoke it
./scripts/run_local.sh invoke
```

### Option 3: Docker Container

```bash
# Build and run in Docker
./scripts/run_local.sh docker

# In another terminal, invoke
curl -X POST http://localhost:8080/invocations \
  -H "Content-Type: application/json" \
  -d '{"mode": "proactive"}'
```

### Option 4: AgentCore Dev Server (Hot Reload)

```bash
# Requires bedrock-agentcore-starter-toolkit
pip install bedrock-agentcore-starter-toolkit

./scripts/run_local.sh dev
```

### Local Script Reference

```bash
./scripts/run_local.sh [mode]

Modes:
  direct          Run workflow directly (default)
  server [port]   Start AgentCore server
  dev             Start with hot reload
  docker          Run in Docker container
  invoke [port]   Invoke running server
  health [port]   Check server health
```

## AWS Deployment

### Prerequisites

1. **AWS CLI** configured with appropriate permissions
2. **bedrock-agentcore-starter-toolkit** installed:
   ```bash
   pip install bedrock-agentcore-starter-toolkit
   ```
3. **IAM Execution Role** for AgentCore with permissions:
   - `bedrock:InvokeModel`
   - `s3:PutObject`, `s3:GetObject`
   - `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents`

### Step 1: Configure Environment

Update `.env` with your credentials, then add deployment config:

```bash
export EXECUTION_ROLE_ARN="arn:aws:iam::YOUR_ACCOUNT:role/AgentCoreExecutionRole"
export AWS_REGION="us-east-1"
export AGENT_NAME="aiops-proactive-workflow"
```

### Step 2: Deploy

```bash
# Configure and deploy in one command
./scripts/deploy.sh

# Or step by step
./scripts/deploy.sh configure
./scripts/deploy.sh deploy
```

### Step 3: Verify

```bash
# Check status
./scripts/deploy.sh status

# Test invocation
./scripts/deploy.sh invoke
```

### Step 4: Configure EventBridge

Create an EventBridge rule to trigger the workflow on schedule:

```bash
# Get the Runtime ARN from status output
./scripts/deploy.sh status

# Create EventBridge rule (daily at 6 AM UTC)
aws events put-rule \
  --name "aiops-daily-proactive" \
  --schedule-expression "cron(0 6 * * ? *)" \
  --state ENABLED

# Create IAM role for EventBridge to invoke AgentCore
# (See IAM section below)

# Add target
aws events put-targets \
  --rule "aiops-daily-proactive" \
  --targets '[{
    "Id": "aiops-runtime",
    "Arn": "arn:aws:bedrock-agentcore:REGION:ACCOUNT:runtime/RUNTIME_ID",
    "RoleArn": "arn:aws:iam::ACCOUNT:role/EventBridgeAgentCoreRole",
    "Input": "{\"mode\": \"proactive\"}"
  }]'
```

### Deployment Script Reference

```bash
./scripts/deploy.sh [command]

Commands:
  configure   Configure the AgentCore agent
  deploy      Deploy to AgentCore
  status      Check deployment status
  invoke      Invoke the deployed agent
  destroy     Destroy the deployment
  all         Configure and deploy (default)

Environment Variables:
  AGENT_NAME          Agent name (default: aiops-proactive-workflow)
  AWS_REGION          AWS region (default: us-east-1)
  EXECUTION_ROLE_ARN  IAM role ARN for AgentCore
  DEPLOYMENT_TYPE     container or direct_code_deploy (default: container)
```

### IAM Roles

#### AgentCore Execution Role

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": ["s3:PutObject", "s3:GetObject"],
      "Resource": "arn:aws:s3:::YOUR_BUCKET/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "*"
    }
  ]
}
```

Trust relationship:
```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"Service": "bedrock.amazonaws.com"},
    "Action": "sts:AssumeRole"
  }]
}
```

#### EventBridge Role

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": "bedrock-agentcore:InvokeRuntime",
    "Resource": "arn:aws:bedrock-agentcore:REGION:ACCOUNT:runtime/*"
  }]
}
```

Trust relationship:
```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"Service": "events.amazonaws.com"},
    "Action": "sts:AssumeRole"
  }]
}
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
- Database connection pool exhaustion

## Suggested Fixes
### 1. ConnectionRefused
**Issue:** Service connection failure
**Fix:** Implement retry logic with exponential backoff
**Prevention:** Use connection pools and health checks
```

## Configuration

### Workflow Settings (config/settings.yaml)

```yaml
workflow:
  default_time_from: "now-1d"
  default_time_to: "now"
  max_workers: 50
```

## Project Structure

```
aiops-proactive-workflow/
├── config/
│   ├── settings.yaml      # Workflow and global settings
│   ├── agents.yaml        # Agent configurations
│   └── tools.yaml         # Tool configurations
├── scripts/
│   ├── run_local.sh       # Local development script
│   └── deploy.sh          # AWS deployment script
├── src/
│   ├── agents/
│   │   ├── base.py
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
│   │   ├── swarm_coordinator.py
│   │   └── proactive_workflow.py
│   ├── utils/
│   │   ├── config_loader.py
│   │   └── logging_config.py
│   └── main.py
├── tests/
├── Dockerfile
├── .dockerignore
├── requirements.txt
└── .env.example
```

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
