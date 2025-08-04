#!/bin/bash

# GCS HMAC Key Rotator Deployment Script
# This script builds the container image and deploys the Kubernetes resources

set -euo pipefail

# Configuration
PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project)}"
REGION="${REGION:-us-central1}"
CLUSTER_NAME="${CLUSTER_NAME:-your-gke-cluster}"
SERVICE_ACCOUNT_EMAIL="${SERVICE_ACCOUNT_EMAIL:-hmac-rotator@${PROJECT_ID}.iam.gserviceaccount.com}"
IMAGE_NAME="gcr.io/${PROJECT_ID}/hmac-rotator"
IMAGE_TAG="${IMAGE_TAG:-latest}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
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
    log_info "Checking prerequisites..."
    
    # Check if required tools are installed
    for tool in gcloud docker kubectl; do
        if ! command -v "$tool" &> /dev/null; then
            log_error "$tool is not installed or not in PATH"
            exit 1
        fi
    done
    
    # Check if authenticated with gcloud
    if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
        log_error "Not authenticated with gcloud. Run 'gcloud auth login'"
        exit 1
    fi
    
    # Check if Docker is running
    if ! docker info &> /dev/null; then
        log_error "Docker is not running"
        exit 1
    fi
    
    log_info "Prerequisites check passed"
}

build_and_push_image() {
    log_info "Building container image..."
    
    # Configure Docker to use gcloud as a credential helper
    gcloud auth configure-docker --quiet
    
    # Build the image
    docker build -t "${IMAGE_NAME}:${IMAGE_TAG}" .
    
    log_info "Pushing image to Container Registry..."
    docker push "${IMAGE_NAME}:${IMAGE_TAG}"
    
    log_info "Image pushed successfully: ${IMAGE_NAME}:${IMAGE_TAG}"
}

setup_workload_identity() {
    log_info "Setting up Workload Identity..."
    
    # Get GKE cluster credentials
    gcloud container clusters get-credentials "$CLUSTER_NAME" --region="$REGION" --project="$PROJECT_ID"
    
    # Allow the Kubernetes service account to impersonate the Google service account
    gcloud iam service-accounts add-iam-policy-binding \
        --role roles/iam.workloadIdentityUser \
        --member "serviceAccount:${PROJECT_ID}.svc.id.goog[default/hmac-rotator-sa]" \
        "$SERVICE_ACCOUNT_EMAIL"
    
    log_info "Workload Identity setup completed"
}

update_kubernetes_manifests() {
    log_info "Updating Kubernetes manifests with actual values..."
    
    # Create temporary directory for updated manifests
    TEMP_DIR=$(mktemp -d)
    cp -r k8s/* "$TEMP_DIR/"
    
    # Replace placeholders in manifests
    find "$TEMP_DIR" -name "*.yaml" -exec sed -i.bak \
        -e "s|YOUR_PROJECT_ID|${PROJECT_ID}|g" \
        -e "s|YOUR_SERVICE_ACCOUNT_EMAIL@YOUR_PROJECT_ID.iam.gserviceaccount.com|${SERVICE_ACCOUNT_EMAIL}|g" \
        -e "s|gcr.io/YOUR_PROJECT_ID/hmac-rotator:latest|${IMAGE_NAME}:${IMAGE_TAG}|g" \
        {} \;
    
    # Remove backup files
    find "$TEMP_DIR" -name "*.bak" -delete
    
    echo "$TEMP_DIR"
}

deploy_kubernetes_resources() {
    log_info "Deploying Kubernetes resources..."
    
    # Update manifests with actual values
    MANIFEST_DIR=$(update_kubernetes_manifests)
    
    # Apply the manifests
    kubectl apply -f "$MANIFEST_DIR/serviceaccount.yaml"
    kubectl apply -f "$MANIFEST_DIR/configmap.yaml"
    kubectl apply -f "$MANIFEST_DIR/cronjob.yaml"
    
    # Clean up temporary directory
    rm -rf "$MANIFEST_DIR"
    
    log_info "Kubernetes resources deployed successfully"
}

run_manual_job() {
    log_info "Running manual test job..."
    
    # Update manifests with actual values
    MANIFEST_DIR=$(update_kubernetes_manifests)
    
    # Apply the job manifest
    kubectl apply -f "$MANIFEST_DIR/job.yaml"
    
    # Wait for job completion
    log_info "Waiting for job to complete..."
    kubectl wait --for=condition=complete --timeout=300s job/hmac-rotator-manual
    
    # Show job logs
    log_info "Job logs:"
    kubectl logs job/hmac-rotator-manual
    
    # Clean up the job
    kubectl delete job hmac-rotator-manual
    
    # Clean up temporary directory
    rm -rf "$MANIFEST_DIR"
    
    log_info "Manual job completed successfully"
}

show_status() {
    log_info "Deployment status:"
    echo ""
    echo "Service Account: $SERVICE_ACCOUNT_EMAIL"
    echo "Container Image: ${IMAGE_NAME}:${IMAGE_TAG}"
    echo "Project ID: $PROJECT_ID"
    echo ""
    
    log_info "Kubernetes resources:"
    kubectl get serviceaccount hmac-rotator-sa
    kubectl get configmap hmac-rotator-config
    kubectl get cronjob hmac-rotator-cronjob
    echo ""
    
    log_info "CronJob schedule:"
    kubectl get cronjob hmac-rotator-cronjob -o jsonpath='{.spec.schedule}'
    echo ""
}

main() {
    log_info "Starting GCS HMAC Key Rotator deployment"
    
    case "${1:-all}" in
        "check")
            check_prerequisites
            ;;
        "build")
            check_prerequisites
            build_and_push_image
            ;;
        "deploy")
            setup_workload_identity
            deploy_kubernetes_resources
            ;;
        "test")
            run_manual_job
            ;;
        "status")
            show_status
            ;;
        "all")
            check_prerequisites
            build_and_push_image
            setup_workload_identity
            deploy_kubernetes_resources
            show_status
            ;;
        *)
            echo "Usage: $0 {check|build|deploy|test|status|all}"
            echo ""
            echo "Commands:"
            echo "  check   - Check prerequisites"
            echo "  build   - Build and push container image"
            echo "  deploy  - Deploy Kubernetes resources"
            echo "  test    - Run a manual test job"
            echo "  status  - Show deployment status"
            echo "  all     - Run all steps (default)"
            exit 1
            ;;
    esac
    
    log_info "Operation completed successfully"
}

main "$@"
