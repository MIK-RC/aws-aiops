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
git clone <repository-url>
cd aiops-proactive-workflow
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

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

## Local Testing

### Run Workflow Directly

```bash
python -m src.main --mode proactive
```

### Start Local Server

```bash
# Start server
python -m src.main --serve --port 8080

# Invoke (in another terminal)
curl -X POST http://localhost:8080/invocations \
  -H "Content-Type: application/json" \
  -d '{"mode": "proactive"}'
```

### Run with Docker

```bash
docker build -t aiops-proactive-workflow .
docker run -p 8080:8080 aiops-proactive-workflow
```

## AWS Deployment

### Prerequisites

1. **AWS CLI** configured with appropriate permissions
2. **Starter toolkit** installed:
   ```bash
   pip install bedrock-agentcore-starter-toolkit
   ```
3. **IAM Execution Role** for AgentCore (see IAM section below)

### Step 1: Configure

Set deployment variables in `.env` or export them:

```bash
export EXECUTION_ROLE_ARN="arn:aws:iam::YOUR_ACCOUNT:role/AgentCoreExecutionRole"
export AWS_REGION="us-east-1"
```

### Step 2: Deploy

```bash
./scripts/deploy.sh
```

This will:
1. Configure the AgentCore agent
2. Build container in AWS (via CodeBuild)
3. Deploy to AgentCore Runtime
4. Return the Runtime ARN

### Step 3: Verify

```bash
./scripts/deploy.sh status
./scripts/deploy.sh invoke
```

### Step 4: Configure EventBridge

```bash
# Create rule (daily at 6 AM UTC)
aws events put-rule \
  --name "aiops-daily-proactive" \
  --schedule-expression "cron(0 6 * * ? *)" \
  --state ENABLED

# Add target (use Runtime ARN from deploy output)
aws events put-targets \
  --rule "aiops-daily-proactive" \
  --targets '[{
    "Id": "aiops-runtime",
    "Arn": "arn:aws:bedrock-agentcore:REGION:ACCOUNT:runtime/RUNTIME_ID",
    "RoleArn": "arn:aws:iam::ACCOUNT:role/EventBridgeAgentCoreRole",
    "Input": "{\"mode\": \"proactive\"}"
  }]'
```

### Deployment Script

```bash
./scripts/deploy.sh [command]

Commands:
  configure   Configure the AgentCore agent
  deploy      Deploy to AgentCore
  status      Check deployment status
  invoke      Invoke the deployed agent
  destroy     Destroy the deployment
  all         Configure and deploy (default)
```

### IAM Roles

#### AgentCore Execution Role

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": ["s3:PutObject", "s3:GetObject"],
      "Resource": "arn:aws:s3:::YOUR_BUCKET/*"
    },
    {
      "Effect": "Allow",
      "Action": ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
      "Resource": "*"
    }
  ]
}
```

Trust: `bedrock.amazonaws.com`

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

Trust: `events.amazonaws.com`

## Project Structure

```
aiops-proactive-workflow/
├── config/
│   ├── settings.yaml
│   ├── agents.yaml
│   └── tools.yaml
├── scripts/
│   └── deploy.sh
├── src/
│   ├── agents/
│   ├── tools/
│   ├── workflows/
│   ├── utils/
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
| DATADOG_API_KEY | Yes | DataDog API key |
| DATADOG_APP_KEY | Yes | DataDog App key |
| DATADOG_SITE | No | Default: us5 |
| SERVICENOW_INSTANCE | Yes | ServiceNow URL |
| SERVICENOW_USER | Yes | ServiceNow username |
| SERVICENOW_PASS | Yes | ServiceNow password |
| S3_REPORTS_BUCKET | Yes | S3 bucket for reports |
| AWS_DEFAULT_REGION | No | Default: us-east-1 |

## License

MIT License
