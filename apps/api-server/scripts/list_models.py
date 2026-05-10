import os
import sys
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from google import genai

load_dotenv()

try:
    client = genai.Client()
    # Fetch all first to avoid streaming issues
    models = list(client.models.list())
    for m in models:
        print(m.name)
except Exception as e:
    print(f"Error: {e}")
