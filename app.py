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
            self.secret_name = os.getenv('SECRET_NAME', 'gcs-hmac-key')
            self.max_versions_to_keep = int(os.getenv('MAX_VERSIONS_TO_KEEP', '2'))
            
            if not self.service_account_email:
                raise ValueError("SERVICE_ACCOUNT_EMAIL environment variable is required")
                
            logger.info(f"Service Account: {self.service_account_email}")
            logger.info(f"Secret Name: {self.secret_name}")
            
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
                        "managed-by": "auto-rotation"
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
            
            # Prepare the secret payload
            secret_payload = {
                'access_id': hmac_key_data['access_id'],
                'secret_key': hmac_key_data['secret'],
                'service_account_email': hmac_key_data['service_account_email'],
                'created_time': hmac_key_data['created_time'],
                'rotation_time': datetime.now(timezone.utc).isoformat()
            }
            
            # Convert to JSON string
            secret_data = json.dumps(secret_payload, indent=2)
            
            # Add the secret version
            parent = f"projects/{self.project_id}/secrets/{self.secret_name}"
            payload = {"data": secret_data.encode('utf-8')}
            
            response = self.secret_client.add_secret_version(
                request={
                    "parent": parent,
                    "payload": payload
                }
            )
            
            logger.info(f"Stored HMAC key in secret version: {response.name}")
            
        except Exception as e:
            logger.error(f"Failed to store HMAC key in secret: {e}")
            raise

    def disable_old_secret_versions(self) -> None:
        """Disable old versions of the secret, keeping only the latest ones."""
        try:
            logger.info("Managing old secret versions...")
            
            parent = f"projects/{self.project_id}/secrets/{self.secret_name}"
            
            # List all versions
            versions = self.secret_client.list_secret_versions(
                request={"parent": parent}
            )
            
            # Filter enabled versions and sort by creation time (newest first)
            enabled_versions = [
                v for v in versions 
                if v.state == secretmanager.SecretVersion.State.ENABLED
            ]
            enabled_versions.sort(key=lambda x: x.create_time, reverse=True)
            
            # Disable versions beyond the keep limit
            versions_to_disable = enabled_versions[self.max_versions_to_keep:]
            
            for version in versions_to_disable:
                logger.info(f"Disabling secret version: {version.name}")
                self.secret_client.disable_secret_version(
                    request={"name": version.name}
                )
            
            logger.info(f"Disabled {len(versions_to_disable)} old secret versions")
            
        except Exception as e:
            logger.error(f"Failed to disable old secret versions: {e}")
            raise

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
            
            # Ensure secret exists
            self.ensure_secret_exists()
            
            # Create new HMAC key
            hmac_key_data = self.create_hmac_key()
            
            # Store in Secret Manager
            self.store_hmac_key_in_secret(hmac_key_data)
            
            # Disable old secret versions
            self.disable_old_secret_versions()
            
            # Clean up old HMAC keys
            self.cleanup_old_hmac_keys()
            
            logger.info("HMAC key rotation completed successfully!")
            
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
