# GCS HMAC Key Auto-Rotation with GKE

This project provides an automated solution for creating and rotating GCS HMAC keys using Google Secret Manager while following least privilege principles.

## Quick Local Testing

For immediate testing with your GCP project `tflabs` and bucket `mevijays`:

```bash
# 1. Setup local environment
./setup_local.sh setup

# 2. Run HMAC key rotation test
./setup_local.sh test
```

See [LOCAL_DEVELOPMENT.md](LOCAL_DEVELOPMENT.md) for detailed local testing instructions.

## Configuration

The application is configured via environment variables in `.env`:

- **PROJECT_ID**: `tflabs` 
- **BUCKET_NAME**: `mevijays`
- **SECRET_NAME**: `test`
- **SERVICE_ACCOUNT_EMAIL**: `hmac-rotator@tflabs.iam.gserviceaccount.com`

## Architecture

- **GKE Cluster**: Standard cluster with Workload Identity Federation enabled
- **Service Account**: Google Service Account without direct key management
- **Workload Identity**: Maps Kubernetes Service Account to Google Service Account
- **Automation**: Kubernetes CronJob that runs every 90 days
- **Security**: Follows least privilege policy with minimal IAM permissions

## Components

1. `app.py` - Python application for HMAC key management
2. `Dockerfile` - Container image definition
3. `k8s/` - Kubernetes manifests
4. `terraform/` - Infrastructure as Code (optional)
5. `requirements.txt` - Python dependencies

## Setup Instructions

### Prerequisites

1. GKE cluster with Workload Identity enabled
2. Google Service Account created (without keys)
3. Google Secret Manager API enabled
4. Cloud Storage API enabled

### Deployment

1. Build and push the container image
2. Apply Kubernetes manifests
3. Configure IAM bindings for Workload Identity

### IAM Permissions Required

The Google Service Account needs the following permissions:
- `storage.hmacKeys.create`
- `storage.hmacKeys.list`
- `storage.hmacKeys.update`
- `secretmanager.versions.add`
- `secretmanager.versions.list`
- `secretmanager.versions.disable`

## Usage

The CronJob will automatically:
1. Create new HMAC keys for the service account
2. Store the new key in Google Secret Manager
3. Disable old versions of the secret
4. Clean up old HMAC keys

## Monitoring

Check the job logs for execution status and any errors.
