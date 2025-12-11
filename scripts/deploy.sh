#!/bin/bash
#
# Deployment Script for AIOps Multi-Agent System
#
# Usage:
#   ./scripts/deploy.sh [agentcore|lambda] [--region REGION]
#

set -e

# Default values
REGION="${AWS_REGION:-us-east-1}"
DEPLOYMENT_TYPE="agentcore"
ECR_REPO_NAME="aiops-multi-agent"
LAMBDA_FUNCTION_NAME="aiops-daily-analysis"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        agentcore|lambda)
            DEPLOYMENT_TYPE="$1"
            shift
            ;;
        --region)
            REGION="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo "======================================"
echo "AIOps Multi-Agent System Deployment"
echo "======================================"
echo "Deployment Type: $DEPLOYMENT_TYPE"
echo "Region: $REGION"
echo ""

# Get AWS account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_URI="$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$ECR_REPO_NAME"

echo "Account ID: $ACCOUNT_ID"
echo "ECR URI: $ECR_URI"
echo ""

# Create ECR repository if it doesn't exist
echo "Ensuring ECR repository exists..."
aws ecr describe-repositories --repository-names $ECR_REPO_NAME --region $REGION 2>/dev/null || \
    aws ecr create-repository --repository-name $ECR_REPO_NAME --region $REGION

# Login to ECR
echo "Logging in to ECR..."
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ECR_URI

# Build and push Docker image
echo "Building Docker image..."
if [ "$DEPLOYMENT_TYPE" == "agentcore" ]; then
    docker build -t $ECR_REPO_NAME:latest -f deployment/agentcore/Dockerfile .
else
    docker build -t $ECR_REPO_NAME:latest -f deployment/lambda/Dockerfile .
fi

echo "Tagging image..."
docker tag $ECR_REPO_NAME:latest $ECR_URI:latest

echo "Pushing image to ECR..."
docker push $ECR_URI:latest

echo ""
echo "======================================"
echo "Deployment Complete!"
echo "======================================"
echo "Image: $ECR_URI:latest"
echo ""

if [ "$DEPLOYMENT_TYPE" == "agentcore" ]; then
    echo "Next steps for AgentCore deployment:"
    echo "1. Configure AgentCore with the image URI"
    echo "2. Set environment variables for API keys"
    echo "3. Configure IAM roles and permissions"
else
    echo "Next steps for Lambda deployment:"
    echo "1. Update Lambda function with new image:"
    echo "   aws lambda update-function-code \\"
    echo "     --function-name $LAMBDA_FUNCTION_NAME \\"
    echo "     --image-uri $ECR_URI:latest \\"
    echo "     --region $REGION"
    echo ""
    echo "2. Set environment variables:"
    echo "   aws lambda update-function-configuration \\"
    echo "     --function-name $LAMBDA_FUNCTION_NAME \\"
    echo "     --environment Variables={DATADOG_API_KEY=xxx,SERVICENOW_INSTANCE=xxx}"
fi
