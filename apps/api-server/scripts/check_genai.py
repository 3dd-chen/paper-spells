#!/usr/bin/env python3
"""
Utility script: verify that GCP / Gemini credentials are working.
Run from the api-server root:  python scripts/check_genai.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from google import genai

try:
    client = genai.Client()
    ops = client.operations
    print(f"✅  Gemini client initialised. Available operations: {[m for m in dir(ops) if not m.startswith('_')]}")
except Exception as e:
    print(f"❌  Gemini error: {e}")
    sys.exit(1)
