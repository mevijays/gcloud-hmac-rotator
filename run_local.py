#!/usr/bin/env python3
"""
Local runner script for HMAC key rotation

This script loads environment variables from .env file and runs the rotation locally.
"""

import os
import sys
from pathlib import Path

def load_env_file(env_path: str = ".env"):
    """Load environment variables from .env file."""
    env_file = Path(env_path)
    if not env_file.exists():
        print(f"Warning: {env_path} file not found")
        return
    
    print(f"Loading environment variables from {env_path}")
    with open(env_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip()
                print(f"  {key.strip()}={value.strip()}")

def main():
    """Main function to run local HMAC rotation."""
    print("🚀 Starting local HMAC key rotation...")
    print("=" * 50)
    
    # Load environment variables
    load_env_file()
    print()
    
    # Import and run the main application
    try:
        # Add current directory to Python path and import
        current_dir = os.path.dirname(os.path.abspath(__file__))
        if current_dir not in sys.path:
            sys.path.insert(0, current_dir)
        
        # Import the HMACKeyRotator class from app-dev module
        import importlib.util
        spec = importlib.util.spec_from_file_location("app_dev", os.path.join(current_dir, "app-dev.py"))
        app_dev = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(app_dev)
        
        HMACKeyRotator = app_dev.HMACKeyRotator
        
        print("📋 Configuration Summary:")
        print(f"  Project ID: {os.getenv('PROJECT_ID', 'Not set')}")
        print(f"  Service Account: {os.getenv('SERVICE_ACCOUNT_EMAIL', 'Not set')}")
        print(f"  Bucket Name: {os.getenv('BUCKET_NAME', 'Not set')}")
        print(f"  Secret Name: {os.getenv('SECRET_NAME', 'Not set')}")
        print(f"  Region: {os.getenv('REGION', 'Not set')}")
        print()
        
        # Initialize and run the rotator
        rotator = HMACKeyRotator()
        rotator.rotate_hmac_key()
        
        print("\n🎉 Local HMAC key rotation completed successfully!")
        
    except KeyboardInterrupt:
        print("\n⚠️ Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error during rotation: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
