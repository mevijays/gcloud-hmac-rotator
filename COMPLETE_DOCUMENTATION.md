# GCS HMAC Key Auto-Rotation Solution

## Complete Solution Overview

This repository provides a production-ready solution for automatically rotating GCS HMAC keys using Google Secret Manager while following security best practices and least privilege principles.

### Key Features

- ✅ **Workload Identity Federation**: No service account keys stored in containers
- ✅ **Least Privilege**: Custom IAM role with minimal required permissions
- ✅ **Automated Rotation**: CronJob runs every 90 days
- ✅ **Secret Management**: Stores keys in Google Secret Manager with versioning
- ✅ **Security Hardened**: Non-root containers, read-only filesystem
- ✅ **Infrastructure as Code**: Terraform for reproducible deployments
- ✅ **Monitoring Ready**: Structured logging and error handling

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   GKE Cluster   │    │ Google Cloud    │    │ Secret Manager  │
│                 │    │ Service Account │    │                 │
│ ┌─────────────┐ │    │                 │    │ ┌─────────────┐ │
│ │ K8s SA      │◄┼────┤ Workload        │    │ │ HMAC Keys   │ │
│ │ hmac-rotator│ │    │ Identity        │    │ │ (Versioned) │ │
│ └─────────────┘ │    │ Federation      │    │ └─────────────┘ │
│                 │    │                 │    │                 │
│ ┌─────────────┐ │    └─────────────────┘    └─────────────────┘
│ │ CronJob     │ │             │                       ▲
│ │ (90 days)   │ │             │                       │
│ └─────────────┘ │             ▼                       │
└─────────────────┘    ┌─────────────────┐              │
                       │ Cloud Storage   │              │
                       │ HMAC Keys API   │──────────────┘
                       └─────────────────┘
```

## File Structure

```
.
├── README.md                    # Main documentation
├── SETUP.md                    # Quick setup guide
├── app.py                      # Main Python application
├── requirements.txt            # Python dependencies
├── Dockerfile                  # Container definition
├── docker-compose.yml          # Local testing
├── test_setup.py              # Validation script
├── deploy.sh                  # Deployment automation script
├── .env.example               # Environment variables template
├── .gitignore                 # Git ignore rules
├── k8s/                       # Kubernetes manifests
│   ├── serviceaccount.yaml    # K8s service account with WIF
│   ├── configmap.yaml         # Configuration
│   ├── job.yaml              # Manual job for testing
│   └── cronjob.yaml          # Scheduled rotation job
└── terraform/                 # Infrastructure as Code
    ├── main.tf               # Terraform configuration
    └── terraform.tfvars.example # Terraform variables
```

## Prerequisites

### GCP Setup

1. **GKE Cluster** with Workload Identity enabled:
   ```bash
   gcloud container clusters create your-cluster \
     --workload-pool=PROJECT_ID.svc.id.goog \
     --enable-ip-alias \
     --region=us-central1
   ```

2. **Required APIs**:
   ```bash
   gcloud services enable container.googleapis.com
   gcloud services enable secretmanager.googleapis.com
   gcloud services enable storage.googleapis.com
   gcloud services enable iam.googleapis.com
   ```

### Local Development

1. **Required tools**:
   - `gcloud` CLI
   - `kubectl`
   - `docker`
   - `terraform` (optional)

2. **Authentication**:
   ```bash
   gcloud auth login
   gcloud auth application-default login
   ```

## Installation Methods

### Method 1: Terraform (Recommended)

1. **Configure Terraform**:
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

3. **Deploy application**:
   ```bash
   # Set environment variables from Terraform outputs
   export SERVICE_ACCOUNT_EMAIL=$(terraform output -raw service_account_email)
   export PROJECT_ID=your-project-id
   export CLUSTER_NAME=your-gke-cluster
   
   # Run deployment
   ./deploy.sh all
   ```

### Method 2: Manual Setup

1. **Create Service Account and IAM Role**:
   ```bash
   # Create service account
   gcloud iam service-accounts create hmac-rotator \
     --display-name="HMAC Key Rotator" \
     --description="Service account for automated HMAC key rotation"
   
   # Create custom IAM role
   gcloud iam roles create hmacKeyRotator \
     --project=$PROJECT_ID \
     --title="HMAC Key Rotator Role" \
     --description="Custom role for HMAC key rotation" \
     --permissions="storage.hmacKeys.create,storage.hmacKeys.list,storage.hmacKeys.update,secretmanager.secrets.create,secretmanager.secrets.get,secretmanager.versions.add,secretmanager.versions.list,secretmanager.versions.disable"
   
   # Bind role to service account
   gcloud projects add-iam-policy-binding $PROJECT_ID \
     --member="serviceAccount:hmac-rotator@$PROJECT_ID.iam.gserviceaccount.com" \
     --role="projects/$PROJECT_ID/roles/hmacKeyRotator"
   ```

2. **Deploy application**:
   ```bash
   export PROJECT_ID=your-project-id
   export CLUSTER_NAME=your-gke-cluster
   export SERVICE_ACCOUNT_EMAIL=hmac-rotator@your-project-id.iam.gserviceaccount.com
   
   ./deploy.sh all
   ```

## Usage

### Automated Rotation

The CronJob runs automatically every 90 days. It will:

1. Create a new HMAC key for the service account
2. Store the key details in Google Secret Manager as a new version
3. Disable old versions of the secret (keeping the latest 2)
4. Mark old HMAC keys as INACTIVE

### Manual Execution

To run rotation manually:

```bash
./deploy.sh test
```

### Monitoring

1. **Check CronJob status**:
   ```bash
   kubectl get cronjob hmac-rotator-cronjob
   kubectl describe cronjob hmac-rotator-cronjob
   ```

2. **View job history**:
   ```bash
   kubectl get jobs -l app=hmac-rotator
   ```

3. **Check logs**:
   ```bash
   kubectl logs job/hmac-rotator-cronjob-<timestamp>
   ```

4. **Verify secrets**:
   ```bash
   gcloud secrets list --filter="name:gcs-hmac-key"
   gcloud secrets versions list gcs-hmac-key
   ```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SERVICE_ACCOUNT_EMAIL` | Google Service Account email for HMAC key creation | Required |
| `SECRET_NAME` | Name of the secret in Secret Manager | `gcs-hmac-key` |
| `MAX_VERSIONS_TO_KEEP` | Number of secret versions to keep active | `2` |

### Customizing Rotation Schedule

Edit the CronJob schedule in `k8s/cronjob.yaml`:

```yaml
spec:
  # Current: every 90 days at 2 AM UTC
  schedule: "0 2 */90 * *"
  
  # Other examples:
  # Every 30 days: "0 2 */30 * *"
  # Monthly on 1st: "0 2 1 * *"
  # Weekly: "0 2 * * 0"
```

## Security Considerations

### Least Privilege

The solution follows the principle of least privilege:

- **Custom IAM Role**: Only includes required permissions
- **Workload Identity**: No service account keys in containers
- **Container Security**: Non-root user, read-only filesystem
- **Network**: No unnecessary network access

### Required IAM Permissions

```json
{
  "permissions": [
    "storage.hmacKeys.create",
    "storage.hmacKeys.list", 
    "storage.hmacKeys.update",
    "secretmanager.secrets.create",
    "secretmanager.secrets.get",
    "secretmanager.versions.add",
    "secretmanager.versions.list",
    "secretmanager.versions.disable"
  ]
}
```

### Container Security

- Runs as non-root user (UID 1000)
- Read-only root filesystem
- No privilege escalation
- Drops all capabilities
- Minimal base image (python:3.11-slim)

## Troubleshooting

### Common Issues

1. **Authentication Errors**:
   ```bash
   # Check Workload Identity binding
   gcloud iam service-accounts get-iam-policy $SERVICE_ACCOUNT_EMAIL
   
   # Verify cluster has Workload Identity enabled
   gcloud container clusters describe $CLUSTER_NAME --region=$REGION | grep workloadPool
   ```

2. **Permission Errors**:
   ```bash
   # Check service account permissions
   gcloud projects get-iam-policy $PROJECT_ID \
     --flatten="bindings[].members" \
     --filter="bindings.members:serviceAccount:$SERVICE_ACCOUNT_EMAIL"
   ```

3. **Job Failures**:
   ```bash
   # Check job logs
   kubectl describe job hmac-rotator-manual
   kubectl logs job/hmac-rotator-manual
   ```

4. **Secret Manager Issues**:
   ```bash
   # Verify secret exists
   gcloud secrets describe gcs-hmac-key
   
   # Check secret permissions
   gcloud secrets get-iam-policy gcs-hmac-key
   ```

### Validation Script

Run the validation script to check setup:

```bash
# In the container
kubectl run test-setup --rm -it \
  --image=gcr.io/$PROJECT_ID/hmac-rotator:latest \
  --env="SERVICE_ACCOUNT_EMAIL=$SERVICE_ACCOUNT_EMAIL" \
  --serviceaccount=hmac-rotator-sa \
  --command -- python test_setup.py
```

## Local Development

### Testing Locally

1. **Create service account key** (for local testing only):
   ```bash
   gcloud iam service-accounts keys create service-account-key.json \
     --iam-account=$SERVICE_ACCOUNT_EMAIL
   ```

2. **Run with Docker Compose**:
   ```bash
   # Test setup
   docker-compose run test
   
   # Run rotation
   docker-compose run hmac-rotator
   ```

3. **Clean up**:
   ```bash
   rm service-account-key.json  # Never commit this!
   ```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes and test locally
4. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues and questions:

1. Check the troubleshooting section
2. Review logs and error messages
3. Open an issue with detailed information
4. Include relevant logs and configuration
