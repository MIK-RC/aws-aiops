#!/bin/bash
# ============================================
# AIOps Proactive Workflow - AWS Deployment Script
# ============================================
#
# This script deploys the workflow to AWS Bedrock AgentCore.
#
# Prerequisites:
#   - AWS CLI configured with appropriate permissions
#   - bedrock-agentcore-starter-toolkit installed
#   - .env file with credentials
#
# Usage:
#   ./scripts/deploy.sh [command]
#
# Commands:
#   configure  - Configure the AgentCore agent
#   deploy     - Deploy to AgentCore
#   status     - Check deployment status
#   invoke     - Invoke the deployed agent
#   destroy    - Destroy the deployment
#   all        - Configure and deploy (default)
#
# ============================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

# ============================================
# CONFIGURATION - Update these values
# ============================================

# Agent name (used for AgentCore registration)
AGENT_NAME="${AGENT_NAME:-aiops-proactive-workflow}"

# AWS Region
AWS_REGION="${AWS_REGION:-us-east-1}"

# IAM Execution Role ARN (AgentCore needs this to run)
# Create a role with: Bedrock, S3, CloudWatch Logs permissions
EXECUTION_ROLE_ARN="${EXECUTION_ROLE_ARN:-arn:aws:iam::ACCOUNT_ID:role/AgentCoreExecutionRole}"

# Deployment type: container or direct_code_deploy
DEPLOYMENT_TYPE="${DEPLOYMENT_TYPE:-container}"

# S3 bucket for code (only needed for direct_code_deploy)
AGENTCORE_S3_BUCKET="${AGENTCORE_S3_BUCKET:-}"

# ============================================
# Colors for output
# ============================================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# ============================================
# Load environment variables from .env
# ============================================
load_env() {
    if [ -f ".env" ]; then
        log_info "Loading environment from .env file..."
        set -a
        source .env
        set +a
        log_success "Environment loaded"
    else
        log_warn ".env file not found, using environment variables"
    fi
}

# ============================================
# Build environment flags for agentcore deploy
# ============================================
build_env_flags() {
    local flags=""
    
    # Required variables
    [ -n "$DATADOG_API_KEY" ] && flags="$flags -env DATADOG_API_KEY=$DATADOG_API_KEY"
    [ -n "$DATADOG_APP_KEY" ] && flags="$flags -env DATADOG_APP_KEY=$DATADOG_APP_KEY"
    [ -n "$DATADOG_SITE" ] && flags="$flags -env DATADOG_SITE=$DATADOG_SITE"
    [ -n "$SERVICENOW_INSTANCE" ] && flags="$flags -env SERVICENOW_INSTANCE=$SERVICENOW_INSTANCE"
    [ -n "$SERVICENOW_USER" ] && flags="$flags -env SERVICENOW_USER=$SERVICENOW_USER"
    [ -n "$SERVICENOW_PASS" ] && flags="$flags -env SERVICENOW_PASS=$SERVICENOW_PASS"
    [ -n "$S3_REPORTS_BUCKET" ] && flags="$flags -env S3_REPORTS_BUCKET=$S3_REPORTS_BUCKET"
    
    # Optional variables
    [ -n "$AWS_DEFAULT_REGION" ] && flags="$flags -env AWS_DEFAULT_REGION=$AWS_DEFAULT_REGION"
    
    echo "$flags"
}

# ============================================
# Check prerequisites
# ============================================
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check agentcore CLI
    if ! command -v agentcore &> /dev/null; then
        log_warn "agentcore CLI not found, installing..."
        pip install -q bedrock-agentcore-starter-toolkit
    fi
    
    # Verify agentcore is now available
    if ! command -v agentcore &> /dev/null; then
        # Try with full path
        AGENTCORE_CMD="$HOME/.local/bin/agentcore"
        if [ ! -f "$AGENTCORE_CMD" ]; then
            log_error "Failed to install agentcore CLI"
            exit 1
        fi
    else
        AGENTCORE_CMD="agentcore"
    fi
    
    log_success "agentcore CLI ready"
    
    # Check required env vars
    local missing=""
    [ -z "$DATADOG_API_KEY" ] && missing="$missing DATADOG_API_KEY"
    [ -z "$DATADOG_APP_KEY" ] && missing="$missing DATADOG_APP_KEY"
    [ -z "$SERVICENOW_INSTANCE" ] && missing="$missing SERVICENOW_INSTANCE"
    [ -z "$SERVICENOW_USER" ] && missing="$missing SERVICENOW_USER"
    [ -z "$SERVICENOW_PASS" ] && missing="$missing SERVICENOW_PASS"
    [ -z "$S3_REPORTS_BUCKET" ] && missing="$missing S3_REPORTS_BUCKET"
    
    if [ -n "$missing" ]; then
        log_error "Missing required environment variables:$missing"
        log_info "Set them in .env file or export them"
        exit 1
    fi
    
    log_success "All prerequisites met"
}

# ============================================
# Configure AgentCore agent
# ============================================
do_configure() {
    log_info "Configuring AgentCore agent: $AGENT_NAME"
    
    local s3_flag=""
    if [ -n "$AGENTCORE_S3_BUCKET" ] && [ "$DEPLOYMENT_TYPE" = "direct_code_deploy" ]; then
        s3_flag="-s3 $AGENTCORE_S3_BUCKET"
    fi
    
    $AGENTCORE_CMD configure -c \
        -n "$AGENT_NAME" \
        -e "src/main.py" \
        -dt "$DEPLOYMENT_TYPE" \
        -r "$AWS_REGION" \
        -er "$EXECUTION_ROLE_ARN" \
        $s3_flag \
        -ni
    
    log_success "Agent configured"
}

# ============================================
# Deploy to AgentCore
# ============================================
do_deploy() {
    log_info "Deploying to AgentCore..."
    
    local env_flags=$(build_env_flags)
    
    log_info "Environment variables to be set:"
    echo "  - DATADOG_API_KEY: [set]"
    echo "  - DATADOG_APP_KEY: [set]"
    echo "  - DATADOG_SITE: ${DATADOG_SITE:-us5}"
    echo "  - SERVICENOW_INSTANCE: $SERVICENOW_INSTANCE"
    echo "  - SERVICENOW_USER: $SERVICENOW_USER"
    echo "  - SERVICENOW_PASS: [set]"
    echo "  - S3_REPORTS_BUCKET: $S3_REPORTS_BUCKET"
    echo ""
    
    # Deploy with environment variables
    eval "$AGENTCORE_CMD deploy -a $AGENT_NAME $env_flags -auc"
    
    log_success "Deployment complete!"
    log_info "Run '$0 status' to check the deployment"
}

# ============================================
# Check deployment status
# ============================================
do_status() {
    log_info "Checking deployment status..."
    $AGENTCORE_CMD status -a "$AGENT_NAME"
}

# ============================================
# Invoke the deployed agent
# ============================================
do_invoke() {
    local payload=${1:-'{"mode": "proactive"}'}
    log_info "Invoking agent with payload: $payload"
    $AGENTCORE_CMD invoke -a "$AGENT_NAME" "$payload"
}

# ============================================
# Destroy the deployment
# ============================================
do_destroy() {
    log_warn "This will destroy the AgentCore deployment!"
    read -p "Are you sure? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_info "Destroying deployment..."
        $AGENTCORE_CMD destroy -a "$AGENT_NAME"
        log_success "Deployment destroyed"
    else
        log_info "Cancelled"
    fi
}

# ============================================
# Show usage
# ============================================
show_usage() {
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  configure   Configure the AgentCore agent"
    echo "  deploy      Deploy to AgentCore"
    echo "  status      Check deployment status"
    echo "  invoke      Invoke the deployed agent"
    echo "  destroy     Destroy the deployment"
    echo "  all         Configure and deploy (default)"
    echo ""
    echo "Environment Variables (set in .env or export):"
    echo "  AGENT_NAME          Agent name (default: aiops-proactive-workflow)"
    echo "  AWS_REGION          AWS region (default: us-east-1)"
    echo "  EXECUTION_ROLE_ARN  IAM role ARN for AgentCore"
    echo "  DEPLOYMENT_TYPE     container or direct_code_deploy (default: container)"
    echo ""
    echo "Examples:"
    echo "  $0                  # Configure and deploy"
    echo "  $0 deploy           # Deploy only"
    echo "  $0 status           # Check status"
    echo "  $0 invoke           # Run the workflow"
    echo "  $0 invoke '{\"mode\": \"swarm\", \"task\": \"Analyze auth-service\"}'"
}

# ============================================
# Main
# ============================================
main() {
    local command=${1:-all}
    
    echo "============================================"
    echo "AIOps Proactive Workflow - AWS Deployment"
    echo "============================================"
    echo ""
    
    load_env
    
    case "$command" in
        configure)
            check_prerequisites
            do_configure
            ;;
        deploy)
            check_prerequisites
            do_deploy
            ;;
        status)
            do_status
            ;;
        invoke)
            do_invoke "${2:-'{\"mode\": \"proactive\"}'}"
            ;;
        destroy)
            do_destroy
            ;;
        all)
            check_prerequisites
            do_configure
            do_deploy
            ;;
        help|--help|-h)
            show_usage
            ;;
        *)
            log_error "Unknown command: $command"
            show_usage
            exit 1
            ;;
    esac
}

main "$@"
