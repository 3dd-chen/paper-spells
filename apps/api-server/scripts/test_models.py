import os
import sys
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from google import genai

load_dotenv()

models_to_test = [
    "gemini-3.1-flash-lite",
    "gemini-3.1-flash-lite-preview",
    "gemini-2.5-flash",
    "gemini-1.5-flash"
]

client = genai.Client()

for model in models_to_test:
    print(f"Testing {model}...")
    try:
        response = client.models.generate_content(
            model=model,
            contents="Say 'Hello' and nothing else.",
        )
        print(f"✅ Success! Response: {response.text.strip()}")
    except Exception as e:
        print(f"❌ Failed: {e}")
    print("-" * 40)
