#!/bin/bash
# ============================================
# AIOps Proactive Workflow - Local Run Script
# ============================================
#
# This script provides multiple ways to run the workflow locally:
#   1. Direct Python execution (fastest for development)
#   2. AgentCore dev server (hot reload)
#   3. Docker container (production-like)
#
# Usage:
#   ./scripts/run_local.sh [mode]
#
# Modes:
#   direct    - Run workflow directly (default)
#   server    - Start AgentCore server locally
#   dev       - Start with agentcore dev (hot reload)
#   docker    - Run in Docker container
#   invoke    - Invoke running server
#
# ============================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check for .env file
check_env() {
    if [ ! -f ".env" ]; then
        log_error ".env file not found!"
        log_info "Copy .env.example to .env and configure your credentials:"
        echo "  cp .env.example .env"
        exit 1
    fi
    log_success ".env file found"
}

# Check Python environment
check_python() {
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 not found!"
        exit 1
    fi
    log_info "Python version: $(python3 --version)"
}

# Install dependencies
install_deps() {
    log_info "Installing dependencies..."
    pip install -q -r requirements.txt
    log_success "Dependencies installed"
}

# Mode: Direct execution
run_direct() {
    log_info "Running workflow directly..."
    echo ""
    python3 -m src.main --mode proactive
}

# Mode: Start local server
run_server() {
    local port=${1:-8080}
    log_info "Starting AgentCore server on port $port..."
    log_info "Endpoints:"
    echo "  - POST http://localhost:$port/invocations"
    echo "  - GET  http://localhost:$port/ping"
    echo ""
    log_info "Press Ctrl+C to stop"
    echo ""
    python3 -m src.main --serve --port "$port"
}

# Mode: AgentCore dev server (requires starter toolkit)
run_dev() {
    if ! command -v agentcore &> /dev/null; then
        log_warn "agentcore CLI not found, installing..."
        pip install -q bedrock-agentcore-starter-toolkit
    fi
    log_info "Starting AgentCore dev server with hot reload..."
    agentcore dev
}

# Mode: Docker container
run_docker() {
    log_info "Building Docker image..."
    docker build -t aiops-proactive-workflow:local .
    
    log_info "Running container..."
    log_info "Endpoints:"
    echo "  - POST http://localhost:8080/invocations"
    echo "  - GET  http://localhost:8080/ping"
    echo ""
    docker run --rm -p 8080:8080 aiops-proactive-workflow:local
}

# Mode: Invoke running server
run_invoke() {
    local port=${1:-8080}
    local payload=${2:-'{"mode": "proactive"}'}
    
    log_info "Invoking server at localhost:$port..."
    echo ""
    
    curl -s -X POST "http://localhost:$port/invocations" \
        -H "Content-Type: application/json" \
        -d "$payload" | python3 -m json.tool
}

# Health check
check_health() {
    local port=${1:-8080}
    log_info "Checking health at localhost:$port..."
    curl -s "http://localhost:$port/ping" | python3 -m json.tool
}

# Show usage
show_usage() {
    echo "Usage: $0 [mode] [options]"
    echo ""
    echo "Modes:"
    echo "  direct          Run workflow directly (default)"
    echo "  server [port]   Start AgentCore server (default port: 8080)"
    echo "  dev             Start with hot reload (requires starter toolkit)"
    echo "  docker          Run in Docker container"
    echo "  invoke [port] [payload]   Invoke running server"
    echo "  health [port]   Check server health"
    echo ""
    echo "Examples:"
    echo "  $0                    # Run workflow directly"
    echo "  $0 server             # Start server on port 8080"
    echo "  $0 server 9000        # Start server on port 9000"
    echo "  $0 docker             # Run in Docker"
    echo "  $0 invoke             # Invoke with default payload"
    echo "  $0 invoke 8080 '{\"mode\": \"swarm\", \"task\": \"Check DataDog\"}'"
}

# Main
main() {
    local mode=${1:-direct}
    
    echo "============================================"
    echo "AIOps Proactive Workflow - Local Runner"
    echo "============================================"
    echo ""
    
    check_env
    check_python
    
    case "$mode" in
        direct)
            install_deps
            run_direct
            ;;
        server)
            install_deps
            run_server "${2:-8080}"
            ;;
        dev)
            install_deps
            run_dev
            ;;
        docker)
            run_docker
            ;;
        invoke)
            run_invoke "${2:-8080}" "${3:-'{\"mode\": \"proactive\"}'}"
            ;;
        health)
            check_health "${2:-8080}"
            ;;
        help|--help|-h)
            show_usage
            ;;
        *)
            log_error "Unknown mode: $mode"
            show_usage
            exit 1
            ;;
    esac
}

main "$@"
