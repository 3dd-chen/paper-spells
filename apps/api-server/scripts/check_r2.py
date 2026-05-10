#!/usr/bin/env python3
"""
Utility script: verify that Cloudflare R2 credentials are working.
Run from the api-server root:  python scripts/check_r2.py
"""
import sys
import os

# Make sure `app` package is importable when run from api-server/
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import boto3
from app.config import R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY

r2 = boto3.client(
    service_name="s3",
    endpoint_url=f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
    aws_access_key_id=R2_ACCESS_KEY_ID,
    aws_secret_access_key=R2_SECRET_ACCESS_KEY,
    region_name="auto",
)

try:
    r2.list_buckets()
    print("✅  R2 credentials are valid.")
except Exception as e:
    print(f"❌  R2 error: {e}")
    sys.exit(1)
