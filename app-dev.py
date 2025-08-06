#!/usr/bin/env python3
"""
GCS HMAC Key Auto-Rotation Script

This script automatically creates new HMAC keys for a Google Cloud Storage service account,
stores them in Google Secret Manager, and rotates old keys following security best practices.
"""

import os
import sys
import json
import logging
from datetime import datetime, timezone
from typing import List, Dict, Optional

from google.auth import default
from google.cloud import secretmanager
from google.cloud import storage
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class HMACKeyRotator:
    """Handles HMAC key creation, rotation, and secret management."""
    
    def __init__(self):
        """Initialize the HMAC key rotator with Google Cloud clients."""
        try:
            # Get default credentials (works with Workload Identity)
            self.credentials, self.project_id = default()
            logger.info(f"Authenticated with project: {self.project_id}")
            
            # Initialize clients
            self.secret_client = secretmanager.SecretManagerServiceClient(
                credentials=self.credentials
            )
            self.storage_client = storage.Client(
                credentials=self.credentials,
                project=self.project_id
            )
            
            # Build IAM service for HMAC key management
            self.iam_service = build('storage', 'v1', credentials=self.credentials)
            
            # Get configuration from environment variables
            self.service_account_email = os.getenv('SERVICE_ACCOUNT_EMAIL')
            self.secret_name = os.getenv('SECRET_NAME', 'test')
            self.max_versions_to_keep = int(os.getenv('MAX_VERSIONS_TO_KEEP', '2'))
            self.bucket_name = os.getenv('BUCKET_NAME', 'mevijays')
            self.region = os.getenv('REGION', 'us-east1')
            
            # If no specific service account email is provided, use the default compute service account
            # or derive from project for bucket access
            if not self.service_account_email:
                # For local testing, we'll use the project's default service account
                # You can also specify a specific service account email
                self.service_account_email = f"hmac-rotator@{self.project_id}.iam.gserviceaccount.com"
                logger.info(f"Using default service account: {self.service_account_email}")
            
            logger.info(f"Project ID: {self.project_id}")
            logger.info(f"Service Account: {self.service_account_email}")
            logger.info(f"Secret Name: {self.secret_name}")
            logger.info(f"Bucket Name: {self.bucket_name}")
            logger.info(f"Region: {self.region}")
            
        except Exception as e:
            logger.error(f"Failed to initialize: {e}")
            raise

    def create_hmac_key(self) -> Dict[str, str]:
        """Create a new HMAC key for the service account."""
        try:
            logger.info("Creating new HMAC key...")
            
            request = self.iam_service.projects().hmacKeys().create(
                projectId=self.project_id,
                serviceAccountEmail=self.service_account_email
            )
            
            response = request.execute()
            
            hmac_key_data = {
                'access_id': response['metadata']['accessId'],
                'secret': response['secret'],
                'service_account_email': response['metadata']['serviceAccountEmail'],
                'state': response['metadata']['state'],
                'created_time': response['metadata']['timeCreated']
            }
            
            logger.info(f"Created HMAC key with Access ID: {hmac_key_data['access_id']}")
            return hmac_key_data
            
        except HttpError as e:
            logger.error(f"Failed to create HMAC key: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error creating HMAC key: {e}")
            raise

    def list_hmac_keys(self) -> List[Dict]:
        """List all HMAC keys for the service account."""
        try:
            logger.info("Listing existing HMAC keys...")
            
            request = self.iam_service.projects().hmacKeys().list(
                projectId=self.project_id,
                serviceAccountEmail=self.service_account_email
            )
            
            response = request.execute()
            items = response.get('items', [])
            
            logger.info(f"Found {len(items)} existing HMAC keys")
            return items
            
        except HttpError as e:
            logger.error(f"Failed to list HMAC keys: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error listing HMAC keys: {e}")
            raise

    def update_hmac_key_state(self, access_id: str, state: str) -> None:
        """Update HMAC key state (ACTIVE/INACTIVE)."""
        try:
            logger.info(f"Updating HMAC key {access_id} to state: {state}")
            
            request = self.iam_service.projects().hmacKeys().update(
                projectId=self.project_id,
                accessId=access_id,
                body={'state': state}
            )
            
            request.execute()
            logger.info(f"Successfully updated HMAC key {access_id} to {state}")
            
        except HttpError as e:
            logger.error(f"Failed to update HMAC key {access_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error updating HMAC key {access_id}: {e}")
            raise

    def verify_bucket_access(self) -> bool:
        """Verify that the specified bucket exists and is accessible."""
        try:
            logger.info(f"Verifying access to bucket: {self.bucket_name}")
            
            bucket = self.storage_client.bucket(self.bucket_name)
            
            # Try to get bucket metadata to verify access
            bucket.reload()
            
            logger.info(f"✓ Successfully verified access to bucket: {self.bucket_name}")
            logger.info(f"  Bucket location: {bucket.location}")
            logger.info(f"  Storage class: {bucket.storage_class}")
            
            return True
            
        except Exception as e:
            logger.error(f"✗ Failed to access bucket {self.bucket_name}: {e}")
            logger.error("Make sure the bucket exists and you have proper permissions")
            return False

    def ensure_secret_exists(self) -> None:
        """Ensure the secret exists in Secret Manager."""
        try:
            secret_path = f"projects/{self.project_id}/secrets/{self.secret_name}"
            
            try:
                # Try to get the secret
                self.secret_client.get_secret(request={"name": secret_path})
                logger.info(f"Secret {self.secret_name} already exists")
            except Exception:
                # Secret doesn't exist, create it
                logger.info(f"Creating secret {self.secret_name}...")
                
                parent = f"projects/{self.project_id}"
                secret = {
                    "replication": {"automatic": {}},
                    "labels": {
                        "purpose": "gcs-hmac-key",
                        "managed-by": "auto-rotation",
                        "bucket": self.bucket_name,
                        "project": self.project_id
                    }
                }
                
                self.secret_client.create_secret(
                    request={
                        "parent": parent,
                        "secret_id": self.secret_name,
                        "secret": secret
                    }
                )
                logger.info(f"Created secret {self.secret_name}")
                
        except Exception as e:
            logger.error(f"Failed to ensure secret exists: {e}")
            raise

    def store_hmac_key_in_secret(self, hmac_key_data: Dict[str, str]) -> None:
        """Store the HMAC key data in Google Secret Manager."""
        try:
            logger.info("Storing HMAC key in Secret Manager...")
            
            # Prepare the secret payload with detailed information
            secret_payload = {
                'hmac_credentials': {
                    'access_id': hmac_key_data['access_id'],
                    'secret_key': hmac_key_data['secret'],
                },
                'metadata': {
                    'service_account_email': hmac_key_data['service_account_email'],
                    'bucket_name': self.bucket_name,
                    'project_id': self.project_id,
                    'region': self.region,
                    'created_time': hmac_key_data['created_time'],
                    'rotation_time': datetime.now(timezone.utc).isoformat(),
                    'key_state': hmac_key_data['state']
                },
                'usage_info': {
                    'description': f'HMAC credentials for GCS bucket: {self.bucket_name}',
                    'purpose': 'automated-key-rotation',
                    'managed_by': 'hmac-rotator-script'
                }
            }
            
            # Convert to JSON string with pretty formatting
            secret_data = json.dumps(secret_payload, indent=2, sort_keys=True)
            
            # Add the secret version
            parent = f"projects/{self.project_id}/secrets/{self.secret_name}"
            payload = {"data": secret_data.encode('utf-8')}
            
            response = self.secret_client.add_secret_version(
                request={
                    "parent": parent,
                    "payload": payload
                }
            )
            
            version_name = response.name.split('/')[-1]
            logger.info(f"✓ Stored HMAC key in secret version: {version_name}")
            logger.info(f"  Secret path: {parent}")
            logger.info(f"  Access ID: {hmac_key_data['access_id']}")
            
        except Exception as e:
            logger.error(f"Failed to store HMAC key in secret: {e}")
            raise

    def disable_old_secret_versions(self) -> None:
        """Disable old versions of the secret, keeping only the latest ones."""
        try:
            logger.info("Managing old secret versions...")
            
            parent = f"projects/{self.project_id}/secrets/{self.secret_name}"
            
            # List all versions
            versions = list(self.secret_client.list_secret_versions(
                request={"parent": parent}
            ))
            
            logger.info(f"Found {len(versions)} total secret versions")
            
            # Filter enabled versions and sort by creation time (newest first)
            enabled_versions = [
                v for v in versions 
                if v.state == secretmanager.SecretVersion.State.ENABLED
            ]
            
            logger.info(f"Found {len(enabled_versions)} enabled versions")
            
            # Sort by creation time (newest first)
            enabled_versions.sort(key=lambda x: x.create_time, reverse=True)
            
            # Log all enabled versions for debugging
            for i, version in enumerate(enabled_versions):
                version_number = version.name.split('/')[-1]
                logger.info(f"  Version {i+1}: {version_number} (created: {version.create_time})")
            
            # Only disable if we have more than max_versions_to_keep
            if len(enabled_versions) > self.max_versions_to_keep:
                versions_to_disable = enabled_versions[self.max_versions_to_keep:]
                
                logger.info(f"Will disable {len(versions_to_disable)} versions (keeping latest {self.max_versions_to_keep})")
                
                for version in versions_to_disable:
                    version_number = version.name.split('/')[-1]
                    logger.info(f"Disabling secret version: {version_number}")
                    
                    try:
                        self.secret_client.disable_secret_version(
                            request={"name": version.name}
                        )
                        logger.info(f"✓ Successfully disabled version {version_number}")
                    except Exception as e:
                        logger.error(f"Failed to disable version {version_number}: {e}")
                        # Continue with other versions
                
                logger.info(f"✓ Disabled {len(versions_to_disable)} old secret versions")
            else:
                logger.info(f"Only {len(enabled_versions)} enabled versions found, no need to disable any (keeping {self.max_versions_to_keep})")
            
        except Exception as e:
            logger.error(f"Failed to disable old secret versions: {e}")
            raise

    def list_secret_versions(self) -> None:
        """List all versions of the secret for debugging."""
        try:
            logger.info(f"Listing all versions of secret '{self.secret_name}'...")
            
            parent = f"projects/{self.project_id}/secrets/{self.secret_name}"
            
            versions = list(self.secret_client.list_secret_versions(
                request={"parent": parent}
            ))
            
            if not versions:
                logger.info("No versions found")
                return
            
            # Sort by creation time (newest first)
            versions.sort(key=lambda x: x.create_time, reverse=True)
            
            logger.info(f"Found {len(versions)} total versions:")
            for i, version in enumerate(versions):
                version_number = version.name.split('/')[-1]
                state = secretmanager.SecretVersion.State(version.state).name
                create_time = version.create_time.strftime('%Y-%m-%d %H:%M:%S UTC')
                logger.info(f"  {i+1}. Version {version_number}: {state} (created: {create_time})")
                
        except Exception as e:
            logger.error(f"Failed to list secret versions: {e}")

    def cleanup_old_hmac_keys(self) -> None:
        """Clean up old HMAC keys (set to INACTIVE)."""
        try:
            logger.info("Cleaning up old HMAC keys...")
            
            hmac_keys = self.list_hmac_keys()
            
            # Sort by creation time (oldest first)
            hmac_keys.sort(key=lambda x: x['timeCreated'])
            
            # Keep the latest key active, inactivate others
            if len(hmac_keys) > 1:
                keys_to_inactivate = hmac_keys[:-1]  # All except the last (newest)
                
                for key in keys_to_inactivate:
                    if key['state'] == 'ACTIVE':
                        self.update_hmac_key_state(key['accessId'], 'INACTIVE')
                        
                logger.info(f"Inactivated {len(keys_to_inactivate)} old HMAC keys")
            
        except Exception as e:
            logger.error(f"Failed to cleanup old HMAC keys: {e}")
            raise

    def rotate_hmac_key(self) -> None:
        """Perform the complete HMAC key rotation process."""
        try:
            logger.info("Starting HMAC key rotation process...")
            logger.info(f"Target bucket: {self.bucket_name}")
            logger.info(f"Target secret: {self.secret_name}")
            
            # Verify bucket access first
            if not self.verify_bucket_access():
                raise Exception(f"Cannot access bucket {self.bucket_name}. Aborting rotation.")
            
            # Ensure secret exists
            self.ensure_secret_exists()
            
            # Create new HMAC key
            hmac_key_data = self.create_hmac_key()
            
            # Store in Secret Manager
            self.store_hmac_key_in_secret(hmac_key_data)
            
            # List current versions for debugging
            self.list_secret_versions()
            
            # Disable old secret versions
            self.disable_old_secret_versions()
            
            # List versions after cleanup
            logger.info("After cleanup:")
            self.list_secret_versions()
            
            # Clean up old HMAC keys
            self.cleanup_old_hmac_keys()
            
            logger.info("🎉 HMAC key rotation completed successfully!")
            logger.info(f"✓ New HMAC key created for bucket: {self.bucket_name}")
            logger.info(f"✓ Credentials stored in secret: {self.secret_name}")
            logger.info(f"✓ Old versions disabled (keeping {self.max_versions_to_keep} latest)")
            
        except Exception as e:
            logger.error(f"HMAC key rotation failed: {e}")
            raise

def main():
    """Main function to run the HMAC key rotation."""
    try:
        logger.info("Starting GCS HMAC Key Auto-Rotation")
        
        # Initialize the rotator
        rotator = HMACKeyRotator()
        
        # Perform rotation
        rotator.rotate_hmac_key()
        
        logger.info("HMAC key rotation process completed successfully")
        sys.exit(0)
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
