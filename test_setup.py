#!/usr/bin/env python3
"""
Test script for HMAC Key Rotator

This script validates the setup and tests the HMAC key rotation functionality.
"""

import os
import sys
import json
import time
import logging
from google.auth import default
from google.cloud import secretmanager
from google.cloud import storage
from googleapiclient.discovery import build

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_authentication():
    """Test Google Cloud authentication."""
    try:
        credentials, project_id = default()
        logger.info(f"✓ Authentication successful for project: {project_id}")
        return credentials, project_id
    except Exception as e:
        logger.error(f"✗ Authentication failed: {e}")
        return None, None

def test_secret_manager_access(credentials, project_id):
    """Test Secret Manager access."""
    try:
        client = secretmanager.SecretManagerServiceClient(credentials=credentials)
        
        # Try to list secrets
        parent = f"projects/{project_id}"
        secrets = list(client.list_secrets(request={"parent": parent}))
        
        logger.info(f"✓ Secret Manager access successful. Found {len(secrets)} secrets")
        return True
    except Exception as e:
        logger.error(f"✗ Secret Manager access failed: {e}")
        return False

def test_storage_access(credentials, project_id):
    """Test Cloud Storage access."""
    try:
        client = storage.Client(credentials=credentials, project=project_id)
        
        # Try to list buckets (this tests basic storage access)
        buckets = list(client.list_buckets())
        
        logger.info(f"✓ Cloud Storage access successful. Found {len(buckets)} buckets")
        return True
    except Exception as e:
        logger.error(f"✗ Cloud Storage access failed: {e}")
        return False

def test_hmac_key_permissions(credentials, project_id, service_account_email):
    """Test HMAC key management permissions."""
    try:
        service = build('storage', 'v1', credentials=credentials)
        
        # Try to list HMAC keys
        request = service.projects().hmacKeys().list(
            projectId=project_id,
            serviceAccountEmail=service_account_email
        )
        response = request.execute()
        
        hmac_keys = response.get('items', [])
        logger.info(f"✓ HMAC key permissions valid. Found {len(hmac_keys)} existing keys")
        return True
    except Exception as e:
        logger.error(f"✗ HMAC key permissions failed: {e}")
        return False

def test_environment_variables():
    """Test required environment variables."""
    required_vars = ['SERVICE_ACCOUNT_EMAIL']
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        logger.error(f"✗ Missing environment variables: {', '.join(missing_vars)}")
        return False
    else:
        logger.info("✓ All required environment variables are set")
        return True

def main():
    """Run all tests."""
    logger.info("Starting HMAC Key Rotator validation tests...")
    
    all_tests_passed = True
    
    # Test environment variables
    if not test_environment_variables():
        all_tests_passed = False
    
    # Test authentication
    credentials, project_id = test_authentication()
    if not credentials:
        sys.exit(1)
    
    # Test service access
    if not test_secret_manager_access(credentials, project_id):
        all_tests_passed = False
    
    if not test_storage_access(credentials, project_id):
        all_tests_passed = False
    
    # Test HMAC key permissions
    service_account_email = os.getenv('SERVICE_ACCOUNT_EMAIL')
    if service_account_email:
        if not test_hmac_key_permissions(credentials, project_id, service_account_email):
            all_tests_passed = False
    
    # Summary
    if all_tests_passed:
        logger.info("🎉 All tests passed! The setup is ready for HMAC key rotation.")
        sys.exit(0)
    else:
        logger.error("❌ Some tests failed. Please check the configuration and permissions.")
        sys.exit(1)

if __name__ == "__main__":
    main()
