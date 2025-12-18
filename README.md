# AIOps Proactive Workflow

Multi-agent system for proactive operations management. Analyzes services, creates tickets, and stores reports automatically.

## Architecture

```
EventBridge (scheduled) / API Gateway
        │
        ▼
   AgentCore Runtime
        │
        ▼
┌─────────────────────────────────────────────┐
│  main.py                                     │
│                                              │
│  ├── proactive: Automated daily scan        │
│  │   └── DataDog → Swarm → S3               │
│  │                                           │
│  ├── chat: Interactive troubleshooting      │
│  │   └── Orchestrator (session-based)       │
│  │                                           │
│  └── swarm: One-off task                    │
│      └── Direct swarm execution             │
└─────────────────────────────────────────────┘
```

## Agents

| Agent        | Purpose                       |
| ------------ | ----------------------------- |
| DataDog      | Fetch error/warning logs      |
| Coding       | Analyze errors, suggest fixes |
| ServiceNow   | Create incident tickets       |
| S3           | Upload reports                |
| Orchestrator | Coordinate agents (chat mode) |

## Setup

```bash
# Install
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your credentials
```

## Local Testing

```bash
# Start server
python -m src.main

# Test with curl or Postman
curl -X POST http://localhost:8080/invocations \
  -H "Content-Type: application/json" \
  -d '{"mode": "proactive"}'
```

## API Payloads

### Proactive (automated scan)
```json
{"mode": "proactive"}
```

### Chat (interactive)
```json
{"mode": "chat", "message": "Why is payment-service failing?"}
```

With session:
```json
{"mode": "chat", "session_id": "abc-123", "message": "Create a ticket"}
```

### Swarm (one-off task)
```json
{"mode": "swarm", "task": "Analyze auth-service errors"}
```

## AWS Deployment

### Prerequisites
- AWS CLI configured
- IAM role with Bedrock, S3, CloudWatch permissions

### Deploy

```bash
./scripts/deploy.sh
```

The script reads credentials from `.env` and deploys to AgentCore.

### Check Status

```bash
agentcore status
```

### EventBridge (scheduled trigger)

```bash
aws events put-rule \
  --name "aiops-daily" \
  --schedule-expression "cron(0 6 * * ? *)"

aws events put-targets \
  --rule "aiops-daily" \
  --targets '[{
    "Id": "aiops",
    "Arn": "YOUR_RUNTIME_ARN",
    "Input": "{\"mode\": \"proactive\"}"
  }]'
```

## Environment Variables

| Variable            | Required | Description                   |
| ------------------- | -------- | ----------------------------- |
| DATADOG_API_KEY     | Yes      | DataDog API key               |
| DATADOG_APP_KEY     | Yes      | DataDog App key               |
| SERVICENOW_INSTANCE | Yes      | e.g., company.service-now.com |
| SERVICENOW_USER     | Yes      | ServiceNow username           |
| SERVICENOW_PASS     | Yes      | ServiceNow password           |
| S3_REPORTS_BUCKET   | Yes      | Bucket for reports            |
| EXECUTION_ROLE_ARN  | Yes      | IAM role for AgentCore        |

## Project Structure

```
├── src/
│   ├── main.py              # Entry point
│   ├── agents/              # All agents
│   ├── tools/               # API clients
│   └── workflows/           # Proactive + Swarm
├── config/                  # YAML configs
├── scripts/deploy.sh        # AWS deployment
├── Dockerfile
└── .env.example
```

## License

MIT
