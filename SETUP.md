# Quick Setup Guide

## Prerequisites

1. **GKE Cluster**: Standard cluster with Workload Identity enabled
2. **APIs Enabled**:
   ```bash
   gcloud services enable container.googleapis.com
   gcloud services enable secretmanager.googleapis.com
   gcloud services enable storage.googleapis.com
   gcloud services enable iam.googleapis.com
   ```

## Option 1: Using Terraform (Recommended)

1. **Configure Terraform variables**:
   ```bash
   cd terraform
   cp terraform.tfvars.example terraform.tfvars
   # Edit terraform.tfvars with your values
   ```

2. **Deploy infrastructure**:
   ```bash
   terraform init
   terraform plan
   terraform apply
   ```

3. **Update Kubernetes manifests** with Terraform outputs:
   ```bash
   # Use the service account email from Terraform output
   SERVICE_ACCOUNT_EMAIL=$(terraform output -raw service_account_email)
   ```

## Option 2: Manual Setup

1. **Create Service Account**:
   ```bash
   gcloud iam service-accounts create hmac-rotator \
     --display-name="HMAC Key Rotator" \
     --description="Service account for automated HMAC key rotation"
   ```

2. **Create Custom IAM Role**:
   ```bash
   gcloud iam roles create hmacKeyRotator \
     --project=$PROJECT_ID \
     --title="HMAC Key Rotator Role" \
     --description="Custom role for HMAC key rotation" \
     --permissions="storage.hmacKeys.create,storage.hmacKeys.list,storage.hmacKeys.update,secretmanager.secrets.create,secretmanager.secrets.get,secretmanager.versions.add,secretmanager.versions.list,secretmanager.versions.disable"
   ```

3. **Bind Role to Service Account**:
   ```bash
   gcloud projects add-iam-policy-binding $PROJECT_ID \
     --member="serviceAccount:hmac-rotator@$PROJECT_ID.iam.gserviceaccount.com" \
     --role="projects/$PROJECT_ID/roles/hmacKeyRotator"
   ```

## Deployment

1. **Set environment variables**:
   ```bash
   export PROJECT_ID=your-project-id
   export CLUSTER_NAME=your-gke-cluster
   export SERVICE_ACCOUNT_EMAIL=hmac-rotator@your-project-id.iam.gserviceaccount.com
   ```

2. **Run deployment script**:
   ```bash
   ./deploy.sh all
   ```

   Or step by step:
   ```bash
   ./deploy.sh check    # Check prerequisites
   ./deploy.sh build    # Build and push image
   ./deploy.sh deploy   # Deploy K8s resources
   ./deploy.sh test     # Run test job
   ./deploy.sh status   # Show status
   ```

## Testing

1. **Run manual job**:
   ```bash
   ./deploy.sh test
   ```

2. **Check logs**:
   ```bash
   kubectl logs job/hmac-rotator-manual
   ```

3. **Verify secret creation**:
   ```bash
   gcloud secrets list --filter="name:gcs-hmac-key"
   gcloud secrets versions list gcs-hmac-key
   ```

## Monitoring

1. **Check CronJob status**:
   ```bash
   kubectl get cronjob hmac-rotator-cronjob
   kubectl describe cronjob hmac-rotator-cronjob
   ```

2. **View recent job executions**:
   ```bash
   kubectl get jobs -l app=hmac-rotator
   ```

3. **Check logs of completed jobs**:
   ```bash
   kubectl logs job/hmac-rotator-cronjob-<timestamp>
   ```

## Security Notes

- Service account follows least privilege principle
- Container runs as non-root user
- Read-only root filesystem
- No privilege escalation allowed
- Workload Identity eliminates need for service account keys
