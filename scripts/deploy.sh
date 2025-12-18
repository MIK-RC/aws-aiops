#!/bin/bash
# Deploy to AWS Bedrock AgentCore
# Reads credentials from .env file

set -e
cd "$(dirname "$0")/.."

# Load environment
[ -f .env ] && source .env

# Install CLI if needed
pip install -q bedrock-agentcore-starter-toolkit 2>/dev/null || true

# Configure
agentcore configure -c \
  -n "${AGENT_NAME:-aiops-proactive-workflow}" \
  -e "src/main.py" \
  -dt "container" \
  -r "${AWS_REGION:-us-east-1}" \
  -er "$EXECUTION_ROLE_ARN" \
  -ni

# Deploy
agentcore deploy -a "${AGENT_NAME:-aiops-proactive-workflow}" \
  -env "DATADOG_API_KEY=$DATADOG_API_KEY" \
  -env "DATADOG_APP_KEY=$DATADOG_APP_KEY" \
  -env "DATADOG_SITE=${DATADOG_SITE:-us5}" \
  -env "SERVICENOW_INSTANCE=$SERVICENOW_INSTANCE" \
  -env "SERVICENOW_USER=$SERVICENOW_USER" \
  -env "SERVICENOW_PASS=$SERVICENOW_PASS" \
  -env "S3_REPORTS_BUCKET=$S3_REPORTS_BUCKET" \
  -auc

echo ""
echo "Deployed. Run 'agentcore status' to check."
