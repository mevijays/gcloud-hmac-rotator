# Manual gcloud Commands for HMAC Key Rotator Setup

## Configuration Variables
```bash
export PROJECT_ID="tflabs"
export SERVICE_ACCOUNT_NAME="hmac-rotator"
export SERVICE_ACCOUNT_EMAIL="hmac-rotator@tflabs.iam.gserviceaccount.com"
export CUSTOM_ROLE_ID="hmacKeyRotator"
export SECRET_NAME="test"
export BUCKET_NAME="mevijays"
```

## Step 1: Set Project and Enable APIs

```bash
# Set your project
gcloud config set project tflabs

# Enable required APIs
gcloud services enable storage.googleapis.com secretmanager.googleapis.com iam.googleapis.com
```

## Step 2: Create Custom IAM Role

```bash
# Create custom role with minimal permissions
gcloud iam roles create hmacKeyRotator \
  --project=tflabs \
  --title="HMAC Key Rotator Role" \
  --description="Custom role for HMAC key rotation with minimal required permissions" \
  --permissions="storage.hmacKeys.create,storage.hmacKeys.list,storage.hmacKeys.update,storage.hmacKeys.get,secretmanager.secrets.create,secretmanager.secrets.get,secretmanager.secrets.list,secretmanager.versions.add,secretmanager.versions.list,secretmanager.versions.disable,secretmanager.versions.get,storage.buckets.get,storage.buckets.list" \
  --stage="GA"
```

## Step 3: Create Service Account

```bash
# Create the service account
gcloud iam service-accounts create hmac-rotator \
  --project=tflabs \
  --display-name="HMAC Key Rotator Service Account" \
  --description="Service account for automated GCS HMAC key rotation"
```

## Step 4: Assign Custom Role to Service Account

```bash
# Bind the custom role to the service account
gcloud projects add-iam-policy-binding tflabs \
  --member="serviceAccount:hmac-rotator@tflabs.iam.gserviceaccount.com" \
  --role="projects/tflabs/roles/hmacKeyRotator"
```

## Step 5: Create Secret Manager Secret

```bash
# Create the secret in Secret Manager
gcloud secrets create test \
  --project=tflabs \
  --replication-policy="automatic" \
  --labels="purpose=gcs-hmac-key,managed-by=auto-rotation,bucket=mevijays"
```

## Step 6: Verify Bucket Access

```bash
# Check if bucket exists and is accessible
gsutil ls gs://mevijays

# If bucket doesn't exist, create it
# gsutil mb gs://mevijays
```

## Verification Commands

```bash
# Verify service account exists
gcloud iam service-accounts describe hmac-rotator@tflabs.iam.gserviceaccount.com

# Verify custom role exists
gcloud iam roles describe hmacKeyRotator --project=tflabs

# Verify role binding
gcloud projects get-iam-policy tflabs \
  --flatten="bindings[].members" \
  --filter="bindings.members:serviceAccount:hmac-rotator@tflabs.iam.gserviceaccount.com"

# Verify secret exists
gcloud secrets describe test --project=tflabs

# Test HMAC key permissions
gcloud storage hmac list --service-account-email=hmac-rotator@tflabs.iam.gserviceaccount.com --project=tflabs
```

## Optional: Create Service Account Key for Local Testing

⚠️ **Only for local development - not recommended for production**

```bash
# Create a service account key file (for local testing only)
gcloud iam service-accounts keys create service-account-key.json \
  --iam-account=hmac-rotator@tflabs.iam.gserviceaccount.com

# Set environment variable to use the key
export GOOGLE_APPLICATION_CREDENTIALS="./service-account-key.json"

# Remember to delete the key file after testing
# rm service-account-key.json
```

## Cleanup Commands (if needed)

```bash
# Remove IAM policy binding
gcloud projects remove-iam-policy-binding tflabs \
  --member="serviceAccount:hmac-rotator@tflabs.iam.gserviceaccount.com" \
  --role="projects/tflabs/roles/hmacKeyRotator"

# Delete service account
gcloud iam service-accounts delete hmac-rotator@tflabs.iam.gserviceaccount.com --project=tflabs

# Delete custom role
gcloud iam roles delete hmacKeyRotator --project=tflabs

# Delete secret
gcloud secrets delete test --project=tflabs
```

## Permission Details

The custom role includes these minimal permissions:

**Storage HMAC Keys:**
- `storage.hmacKeys.create` - Create new HMAC keys
- `storage.hmacKeys.list` - List existing HMAC keys  
- `storage.hmacKeys.update` - Update HMAC key state (ACTIVE/INACTIVE)
- `storage.hmacKeys.get` - Get HMAC key details

**Secret Manager:**
- `secretmanager.secrets.create` - Create new secrets
- `secretmanager.secrets.get` - Get secret metadata
- `secretmanager.secrets.list` - List secrets
- `secretmanager.versions.add` - Add new secret versions
- `secretmanager.versions.list` - List secret versions
- `secretmanager.versions.disable` - Disable old versions
- `secretmanager.versions.get` - Get version details

**Storage (for bucket verification):**
- `storage.buckets.get` - Get bucket metadata
- `storage.buckets.list` - List buckets

## Usage After Setup

Once setup is complete, you can run:

```bash
# Test the local application
./setup_local.sh test

# Or run directly
python3 run_local.py
```
