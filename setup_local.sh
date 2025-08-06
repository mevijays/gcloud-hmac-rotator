#!/bin/bash

# Local Development Setup Script for HMAC Key Rotator
# This script helps set up the local environment for testing

set -euo pipefail

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_prerequisites() {
    log_info "Checking prerequisites for local development..."
    
    # Check if Python 3 is installed
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 is not installed"
        exit 1
    fi
    
    # Check if gcloud is installed
    if ! command -v gcloud &> /dev/null; then
        log_error "Google Cloud CLI is not installed"
        log_info "Install from: https://cloud.google.com/sdk/docs/install"
        exit 1
    fi
    
    # Check if authenticated with gcloud
    if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
        log_error "Not authenticated with gcloud"
        log_info "Run: gcloud auth login"
        log_info "Then: gcloud auth application-default login"
        exit 1
    fi
    
    log_info "✓ Prerequisites check passed"
}

setup_python_environment() {
    log_info "Setting up Python environment..."
    
    # Create virtual environment if it doesn't exist
    if [ ! -d "venv" ]; then
        log_info "Creating Python virtual environment..."
        python3 -m venv venv
    fi
    
    # Activate virtual environment
    source venv/bin/activate
    
    # Install requirements
    log_info "Installing Python dependencies..."
    pip install --upgrade pip
    pip install -r requirements.txt
    
    log_info "✓ Python environment setup complete"
}

verify_gcp_access() {
    log_info "Verifying GCP access..."
    
    # Source environment variables
    if [ -f ".env" ]; then
        source .env
    else
        log_error ".env file not found. Please create it from .env.example"
        exit 1
    fi
    
    # Check project access
    if ! gcloud projects describe "$PROJECT_ID" &> /dev/null; then
        log_error "Cannot access project: $PROJECT_ID"
        log_info "Make sure you have access to the project"
        exit 1
    fi
    
    # Check bucket access
    if ! gsutil ls "gs://$BUCKET_NAME" &> /dev/null; then
        log_error "Cannot access bucket: $BUCKET_NAME"
        log_info "Make sure the bucket exists and you have access"
        exit 1
    fi
    
    # Check Secret Manager access
    if ! gcloud secrets describe "$SECRET_NAME" --project="$PROJECT_ID" &> /dev/null; then
        log_warn "Secret '$SECRET_NAME' doesn't exist. It will be created during rotation."
    fi
    
    log_info "✓ GCP access verification complete"
}

run_test() {
    log_info "Running HMAC key rotation test..."
    
    # Activate virtual environment
    source venv/bin/activate
    
    # Run the application
    python3 run_local.py
}

show_usage() {
    cat << EOF
Usage: $0 [COMMAND]

Commands:
  setup     - Set up local development environment
  check     - Check prerequisites and GCP access
  test      - Run HMAC key rotation test
  help      - Show this help message

Examples:
  $0 setup   # First time setup
  $0 check   # Verify configuration
  $0 test    # Run the rotation test

Before running:
1. Copy .env.example to .env and update with your values
2. Make sure you're authenticated with gcloud
3. Ensure you have necessary permissions in GCP
EOF
}

main() {
    case "${1:-help}" in
        "setup")
            check_prerequisites
            setup_python_environment
            verify_gcp_access
            log_info "Setup complete! Run '$0 test' to test the rotation."
            ;;
        "check")
            check_prerequisites
            verify_gcp_access
            ;;
        "test")
            check_prerequisites
            run_test
            ;;
        "help"|*)
            show_usage
            ;;
    esac
}

main "$@"
