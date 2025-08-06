#!/bin/bash

# Manual GCP Setup Script for HMAC Key Rotator
# This script creates service account, custom IAM role, and assigns permissions

set -euo pipefail

# Configuration - Update these values for your environment
PROJECT_ID="tflabs"
SERVICE_ACCOUNT_NAME="hmac-rotator"
SERVICE_ACCOUNT_EMAIL="${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
CUSTOM_ROLE_ID="hmacKeyRotator"
SECRET_NAME="test"
BUCKET_NAME="mevijays"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
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

log_command() {
    echo -e "${BLUE}[COMMAND]${NC} $1"
}

check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check if gcloud is installed
    if ! command -v gcloud &> /dev/null; then
        log_error "gcloud CLI is not installed"
        exit 1
    fi
    
    # Check if authenticated
    if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
        log_error "Not authenticated with gcloud. Run: gcloud auth login"
        exit 1
    fi
    
    # Set project
    log_command "gcloud config set project $PROJECT_ID"
    gcloud config set project "$PROJECT_ID"
    
    log_info "✓ Prerequisites check passed"
}

create_custom_iam_role() {
    log_info "Creating custom IAM role: $CUSTOM_ROLE_ID"
    
    # Check if role already exists
    if gcloud iam roles describe "$CUSTOM_ROLE_ID" --project="$PROJECT_ID" &> /dev/null; then
        log_warn "Custom role '$CUSTOM_ROLE_ID' already exists. Updating it..."
        
        log_command "gcloud iam roles update $CUSTOM_ROLE_ID --project=$PROJECT_ID --file=custom-role.yaml"
        
        # Create role definition file
        cat > custom-role.yaml << EOF
title: "HMAC Key Rotator Role"
description: "Custom role for HMAC key rotation with minimal required permissions"
stage: "GA"
includedPermissions:
- storage.hmacKeys.create
- storage.hmacKeys.list
- storage.hmacKeys.update
- storage.hmacKeys.get
- secretmanager.secrets.create
- secretmanager.secrets.get
- secretmanager.secrets.list
- secretmanager.versions.add
- secretmanager.versions.list
- secretmanager.versions.disable
- secretmanager.versions.get
- storage.buckets.get
- storage.buckets.list
EOF
        
        gcloud iam roles update "$CUSTOM_ROLE_ID" --project="$PROJECT_ID" --file=custom-role.yaml
        rm custom-role.yaml
        
    else
        log_command "gcloud iam roles create $CUSTOM_ROLE_ID"
        
        gcloud iam roles create "$CUSTOM_ROLE_ID" \
            --project="$PROJECT_ID" \
            --title="HMAC Key Rotator Role" \
            --description="Custom role for HMAC key rotation with minimal required permissions" \
            --permissions="storage.hmacKeys.create,storage.hmacKeys.list,storage.hmacKeys.update,storage.hmacKeys.get,secretmanager.secrets.create,secretmanager.secrets.get,secretmanager.secrets.list,secretmanager.versions.add,secretmanager.versions.list,secretmanager.versions.disable,secretmanager.versions.get,storage.buckets.get,storage.buckets.list" \
            --stage="GA"
    fi
    
    log_info "✓ Custom IAM role created/updated: projects/$PROJECT_ID/roles/$CUSTOM_ROLE_ID"
}

create_service_account() {
    log_info "Creating service account: $SERVICE_ACCOUNT_NAME"
    
    # Check if service account already exists
    if gcloud iam service-accounts describe "$SERVICE_ACCOUNT_EMAIL" --project="$PROJECT_ID" &> /dev/null; then
        log_warn "Service account '$SERVICE_ACCOUNT_EMAIL' already exists"
    else
        log_command "gcloud iam service-accounts create $SERVICE_ACCOUNT_NAME"
        
        gcloud iam service-accounts create "$SERVICE_ACCOUNT_NAME" \
            --project="$PROJECT_ID" \
            --display-name="HMAC Key Rotator Service Account" \
            --description="Service account for automated GCS HMAC key rotation"
    fi
    
    log_info "✓ Service account ready: $SERVICE_ACCOUNT_EMAIL"
}

assign_custom_role() {
    log_info "Assigning custom role to service account..."
    
    log_command "gcloud projects add-iam-policy-binding $PROJECT_ID"
    
    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
        --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
        --role="projects/$PROJECT_ID/roles/$CUSTOM_ROLE_ID"
    
    log_info "✓ Custom role assigned to service account"
}

create_secret_manager_secret() {
    log_info "Creating Secret Manager secret: $SECRET_NAME"
    
    # Check if secret already exists
    if gcloud secrets describe "$SECRET_NAME" --project="$PROJECT_ID" &> /dev/null; then
        log_warn "Secret '$SECRET_NAME' already exists"
    else
        log_command "gcloud secrets create $SECRET_NAME"
        
        gcloud secrets create "$SECRET_NAME" \
            --project="$PROJECT_ID" \
            --replication-policy="automatic" \
            --labels="purpose=gcs-hmac-key,managed-by=auto-rotation,bucket=$BUCKET_NAME"
    fi
    
    log_info "✓ Secret Manager secret ready: $SECRET_NAME"
}

verify_bucket_exists() {
    log_info "Verifying bucket access: $BUCKET_NAME"
    
    if gsutil ls "gs://$BUCKET_NAME" &> /dev/null; then
        log_info "✓ Bucket '$BUCKET_NAME' is accessible"
    else
        log_error "Cannot access bucket '$BUCKET_NAME'"
        log_info "Create the bucket with: gsutil mb gs://$BUCKET_NAME"
        exit 1
    fi
}

enable_required_apis() {
    log_info "Enabling required APIs..."
    
    log_command "gcloud services enable storage.googleapis.com secretmanager.googleapis.com iam.googleapis.com"
    
    gcloud services enable \
        storage.googleapis.com \
        secretmanager.googleapis.com \
        iam.googleapis.com \
        --project="$PROJECT_ID"
    
    log_info "✓ Required APIs enabled"
}

verify_setup() {
    log_info "Verifying setup..."
    
    echo ""
    log_info "📋 Setup Summary:"
    echo "  Project ID: $PROJECT_ID"
    echo "  Service Account: $SERVICE_ACCOUNT_EMAIL"
    echo "  Custom Role: projects/$PROJECT_ID/roles/$CUSTOM_ROLE_ID"
    echo "  Secret Name: $SECRET_NAME"
    echo "  Bucket Name: $BUCKET_NAME"
    echo ""
    
    # Test service account permissions
    log_info "Testing HMAC key permissions..."
    if gcloud storage hmac list --service-account-email="$SERVICE_ACCOUNT_EMAIL" --project="$PROJECT_ID" &> /dev/null; then
        log_info "✓ HMAC key permissions working"
    else
        log_warn "⚠️ HMAC key permissions may need time to propagate"
    fi
    
    # Test Secret Manager permissions
    log_info "Testing Secret Manager permissions..."
    if gcloud secrets list --filter="name:$SECRET_NAME" --project="$PROJECT_ID" &> /dev/null; then
        log_info "✓ Secret Manager permissions working"
    else
        log_warn "⚠️ Secret Manager permissions may need time to propagate"
    fi
    
    log_info "✅ Setup verification complete!"
}

show_next_steps() {
    echo ""
    log_info "🎯 Next Steps:"
    echo "1. Wait 1-2 minutes for IAM permissions to propagate"
    echo "2. Test the setup with: ./setup_local.sh test"
    echo "3. Run HMAC rotation with: python3 run_local.py"
    echo ""
    log_info "🔧 Environment Variables Set:"
    echo "export PROJECT_ID=\"$PROJECT_ID\""
    echo "export SERVICE_ACCOUNT_EMAIL=\"$SERVICE_ACCOUNT_EMAIL\""
    echo "export SECRET_NAME=\"$SECRET_NAME\""
    echo "export BUCKET_NAME=\"$BUCKET_NAME\""
}

cleanup_resources() {
    log_warn "Cleaning up resources (if needed)..."
    echo "To remove created resources, run these commands:"
    echo ""
    echo "# Remove IAM policy binding"
    echo "gcloud projects remove-iam-policy-binding $PROJECT_ID \\"
    echo "  --member=\"serviceAccount:$SERVICE_ACCOUNT_EMAIL\" \\"
    echo "  --role=\"projects/$PROJECT_ID/roles/$CUSTOM_ROLE_ID\""
    echo ""
    echo "# Delete service account"
    echo "gcloud iam service-accounts delete $SERVICE_ACCOUNT_EMAIL --project=$PROJECT_ID"
    echo ""
    echo "# Delete custom role"
    echo "gcloud iam roles delete $CUSTOM_ROLE_ID --project=$PROJECT_ID"
    echo ""
    echo "# Delete secret"
    echo "gcloud secrets delete $SECRET_NAME --project=$PROJECT_ID"
}

main() {
    case "${1:-setup}" in
        "setup")
            log_info "🚀 Starting GCP setup for HMAC Key Rotator"
            echo "======================================================="
            check_prerequisites
            enable_required_apis
            verify_bucket_exists
            create_custom_iam_role
            create_service_account
            assign_custom_role
            create_secret_manager_secret
            verify_setup
            show_next_steps
            ;;
        "verify")
            check_prerequisites
            verify_setup
            ;;
        "cleanup")
            cleanup_resources
            ;;
        "help"|*)
            cat << EOF
Usage: $0 [COMMAND]

Commands:
  setup     - Complete GCP setup (default)
  verify    - Verify existing setup
  cleanup   - Show cleanup commands
  help      - Show this help

Configuration (edit at top of script):
  PROJECT_ID: $PROJECT_ID
  SERVICE_ACCOUNT_NAME: $SERVICE_ACCOUNT_NAME
  CUSTOM_ROLE_ID: $CUSTOM_ROLE_ID
  SECRET_NAME: $SECRET_NAME
  BUCKET_NAME: $BUCKET_NAME

Examples:
  $0 setup    # Run complete setup
  $0 verify   # Check current setup
  $0 cleanup  # Show cleanup commands
EOF
            ;;
    esac
}

main "$@"
