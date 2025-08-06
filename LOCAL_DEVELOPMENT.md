# Local Development Guide

## Quick Start for Local Testing

This guide will help you run the HMAC key rotator locally to test with your GCP project `tflabs` and bucket `mevijays`.

### Prerequisites

1. **Google Cloud CLI** installed and authenticated:
   ```bash
   gcloud auth login
   gcloud auth application-default login
   gcloud config set project tflabs
   ```

2. **Python 3.8+** installed on your system

3. **Required GCP permissions** for your user account:
   - `storage.hmacKeys.*` permissions
   - `secretmanager.*` permissions  
   - Access to bucket `mevijays`
   - Access to project `tflabs`

### Setup Steps

1. **Configure environment**:
   ```bash
   # The .env file is already created with your settings:
   # - PROJECT_ID=tflabs
   # - BUCKET_NAME=mevijays 
   # - SECRET_NAME=test
   # - SERVICE_ACCOUNT_EMAIL=hmac-rotator@tflabs.iam.gserviceaccount.com
   
   # Review and modify .env if needed
   cat .env
   ```

2. **Run setup script**:
   ```bash
   ./setup_local.sh setup
   ```

3. **Test the configuration**:
   ```bash
   ./setup_local.sh check
   ```

4. **Run HMAC key rotation**:
   ```bash
   ./setup_local.sh test
   ```

### Manual Steps (Alternative)

If you prefer manual setup:

1. **Create virtual environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application**:
   ```bash
   python3 run_local.py
   ```

### What the Script Does

When you run the HMAC rotation, it will:

1. ✅ **Verify bucket access** to `mevijays`
2. ✅ **Create a new HMAC key** for the service account
3. ✅ **Store credentials** in Secret Manager secret named `test`
4. ✅ **Create new version** of the secret
5. ✅ **Disable old versions** (keeps latest 2 versions active)
6. ✅ **Mark old HMAC keys** as INACTIVE

### Expected Output

```
🚀 Starting local HMAC key rotation...
==================================================
Loading environment variables from .env
  PROJECT_ID=tflabs
  BUCKET_NAME=mevijays
  SECRET_NAME=test
  ...

📋 Configuration Summary:
  Project ID: tflabs
  Service Account: hmac-rotator@tflabs.iam.gserviceaccount.com
  Bucket Name: mevijays
  Secret Name: test
  Region: us-east1

2025-08-06 10:30:00 - INFO - Starting HMAC key rotation process...
2025-08-06 10:30:00 - INFO - Target bucket: mevijays
2025-08-06 10:30:00 - INFO - Target secret: test
2025-08-06 10:30:01 - INFO - ✓ Successfully verified access to bucket: mevijays
2025-08-06 10:30:02 - INFO - Created HMAC key with Access ID: GOOG1...
2025-08-06 10:30:03 - INFO - ✓ Stored HMAC key in secret version: 1
2025-08-06 10:30:04 - INFO - Disabled 0 old secret versions
2025-08-06 10:30:05 - INFO - 🎉 HMAC key rotation completed successfully!

🎉 Local HMAC key rotation completed successfully!
```

### Troubleshooting

#### Authentication Issues
```bash
# Re-authenticate if needed
gcloud auth login
gcloud auth application-default login
```

#### Permission Issues
```bash
# Check your current authentication
gcloud auth list
gcloud config list

# Verify project access
gcloud projects describe tflabs

# Verify bucket access  
gsutil ls gs://mevijays
```

#### Service Account Issues
If the service account `hmac-rotator@tflabs.iam.gserviceaccount.com` doesn't exist:

1. **Option 1**: Create the service account:
   ```bash
   gcloud iam service-accounts create hmac-rotator \
     --display-name="HMAC Key Rotator" \
     --project=tflabs
   ```

2. **Option 2**: Update `.env` with an existing service account email

3. **Option 3**: Use your own email (for testing only):
   ```bash
   # In .env file, change SERVICE_ACCOUNT_EMAIL to your email
   SERVICE_ACCOUNT_EMAIL=$(gcloud config get-value account)
   ```

### Verifying Results

After successful rotation, verify the results:

1. **Check Secret Manager**:
   ```bash
   gcloud secrets versions list test --project=tflabs
   gcloud secrets versions access latest --secret=test --project=tflabs
   ```

2. **Check HMAC keys**:
   ```bash
   gcloud storage hmac list --project=tflabs
   ```

3. **Test the credentials** (optional):
   ```bash
   # Extract credentials from secret and test
   ACCESS_KEY=$(gcloud secrets versions access latest --secret=test --project=tflabs | jq -r '.hmac_credentials.access_id')
   echo "New Access Key: $ACCESS_KEY"
   ```

### Environment Variables Reference

| Variable | Description | Your Value |
|----------|-------------|------------|
| `PROJECT_ID` | GCP Project ID | `tflabs` |
| `BUCKET_NAME` | Target GCS bucket | `mevijays` |
| `SECRET_NAME` | Secret Manager secret name | `test` |
| `SERVICE_ACCOUNT_EMAIL` | Service account for HMAC key | `hmac-rotator@tflabs.iam.gserviceaccount.com` |
| `REGION` | GCP region | `us-east1` |
| `MAX_VERSIONS_TO_KEEP` | Number of active secret versions | `2` |

### Next Steps

Once local testing is successful, you can:
1. Deploy to GKE using the provided Kubernetes manifests
2. Set up the CronJob for automated rotation
3. Configure monitoring and alerting
