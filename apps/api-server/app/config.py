"""
Centralised configuration.  All environment variables are read here
so that the rest of the app never calls os.getenv() directly.
"""
from __future__ import annotations
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env relative to the api-server root (two levels up from this file:
# app/config.py → app/ → api-server/)
_ENV_FILE = Path(__file__).parent.parent / ".env"
load_dotenv(_ENV_FILE)

# ── Database ──────────────────────────────────────────────────────────────────
DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "sqlite+aiosqlite:///./paper_spells.db",
)

# ── AI Provider ───────────────────────────────────────────────────────────────
AI_PROVIDER: str = os.getenv("AI_PROVIDER", "mock")

# ── Cloudflare R2 ─────────────────────────────────────────────────────────────
R2_ACCOUNT_ID: str = os.getenv("R2_ACCOUNT_ID", "")
R2_ACCESS_KEY_ID: str = os.getenv("R2_ACCESS_KEY_ID", "")
R2_SECRET_ACCESS_KEY: str = os.getenv("R2_SECRET_ACCESS_KEY", "")
R2_BUCKET_NAME: str = os.getenv("R2_BUCKET_NAME", "")
R2_PUBLIC_URL: str = os.getenv("R2_PUBLIC_URL", "").rstrip("/")

# ── GCS / Vertex AI ───────────────────────────────────────────────────────────
GCS_OUTPUT_BUCKET_URI: str = os.getenv("GCS_OUTPUT_BUCKET_URI", "").rstrip("/") + "/"

# ── Upload directory (always at api-server/uploads/, regardless of where
#    main.py lives inside the package tree) ────────────────────────────────────
UPLOAD_DIR: Path = Path(__file__).parent.parent / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
