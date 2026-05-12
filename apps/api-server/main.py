from __future__ import annotations
import base64
import uuid
import logging
import os
import sqlite3
from typing import List

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from app.db.repository import ArtworkRepository
from app.providers import AIProvider, MockProvider, GeminiVeoProvider, ProviderStatus
from app.schemas import UploadRequest, UploadResponse, GalleryItem

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Paper Spells API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow all origins for simplicity in Cloud Run
    allow_methods=["*"],
    allow_headers=["*"],
)

# Provider map
_provider_map: dict[str, type[AIProvider]] = {
    "gemini": GeminiVeoProvider,
    "mock": MockProvider,
}

# ── D1 Mock Adapter for Local SQLite ─────────────────────────────────────────
# This allows us to use the same ArtworkRepository on Cloud Run with SQLite!

class D1Result:
    def __init__(self, rows):
        self.rows = rows
    def to_py(self):
        return self.rows

class D1PreparedStatement:
    def __init__(self, conn, sql):
        self.conn = conn
        self.sql = sql
        self.params = []
    
    def bind(self, *params):
        self.params = params
        return self
    
    async def run(self):
        cursor = self.conn.cursor()
        cursor.execute(self.sql, self.params)
        self.conn.commit()
        return D1Result([])
    
    async def all(self):
        cursor = self.conn.cursor()
        cursor.execute(self.sql, self.params)
        rows = cursor.fetchall()
        # Convert sqlite3.Row to dict
        dict_rows = [dict(row) for row in rows]
        return D1Result(dict_rows)

class D1MockAdapter:
    def __init__(self, conn):
        self.conn = conn
    def prepare(self, sql):
        return D1PreparedStatement(self.conn, sql)

# Initialize local SQLite DB if not running on Cloudflare
# Cloud Run disks are ephemeral, so this resets on restart!
# For production, use Cloud SQL or a managed database.
def init_local_db():
    conn = sqlite3.connect("paper_spells.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS artworks (
            id TEXT PRIMARY KEY,
            image_path TEXT,
            status TEXT,
            provider_task_id TEXT,
            facing_direction TEXT,
            video_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    return conn

# Global DB connection for Cloud Run
local_db_conn = None
if not os.getenv("CF_PAGES"): # Simple check if not on Cloudflare
    local_db_conn = init_local_db()


# ── Dependencies ─────────────────────────────────────────────────────────────

def get_repo(request: Request) -> ArtworkRepository:
    # If running on Cloudflare Workers (via asgi.fetch)
    if "env" in request.scope and hasattr(request.scope["env"], "DB"):
        db = request.scope["env"].DB
        return ArtworkRepository(db)
    else:
        # Running on Cloud Run or locally
        return ArtworkRepository(D1MockAdapter(local_db_conn))

def get_provider(request: Request) -> AIProvider:
    # Access the environment variables
    # On Cloud Run, they are in os.environ
    # On Cloudflare, they are in request.scope["env"]
    provider_name = "mock"
    
    if "env" in request.scope and hasattr(request.scope["env"], "AI_PROVIDER"):
        provider_name = request.scope["env"].AI_PROVIDER
    else:
        provider_name = os.getenv("AI_PROVIDER", "mock")
        
    provider_cls = _provider_map.get(provider_name, MockProvider)
    return provider_cls()


# ── Routes ───────────────────────────────────────────────────────────────────

@app.post("/api/upload", response_model=UploadResponse)
async def upload_artwork(
    req: UploadRequest,
    request: Request,
    repo: ArtworkRepository = Depends(get_repo),
    provider: AIProvider = Depends(get_provider),
) -> UploadResponse:
    try:
        image_bytes = base64.b64decode(req.image_data.split(",")[-1])
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid Base64 image data")

    file_id = str(uuid.uuid4())
    
    artwork = await repo.create_artwork(image_path=f"images/{file_id}.png")

    try:
        # Pass request.scope["env"] if it exists (for Cloudflare fallback), otherwise None
        env = request.scope.get("env", None)
        
        provider_task_id, facing_direction = await provider.submit(
            image_bytes=image_bytes,
            file_id=file_id,
            aspect_ratio=req.aspect_ratio,
            env=env
        )
        logger.info(f"[upload] Provider accepted task: {provider_task_id}, direction: {facing_direction}")
        await repo.update_to_generating(artwork["id"], provider_task_id, facing_direction)
        return UploadResponse(task_id=artwork["id"], status="generating")
    except Exception as e:
        logger.error(f"[upload] Provider error for artwork {artwork['id']}: {type(e).__name__}: {e}")
        await repo.update_to_failed(artwork["id"])
        raise HTTPException(status_code=502, detail=f"Provider error: {type(e).__name__}: {e}")


@app.get("/api/gallery", response_model=List[GalleryItem])
async def get_gallery(
    request: Request,
    repo: ArtworkRepository = Depends(get_repo),
    provider: AIProvider = Depends(get_provider),
) -> List[GalleryItem]:
    generating = await repo.get_all_generating()
    env = request.scope.get("env", None)
    
    for artwork in generating:
        if not artwork["provider_task_id"]:
            continue
        try:
            result = await provider.check_status(artwork["provider_task_id"], env=env)
            if result.status == ProviderStatus.COMPLETED and result.video_url:
                await repo.update_to_completed(artwork["id"], result.video_url)
            elif result.status == ProviderStatus.FAILED:
                await repo.update_to_failed(artwork["id"])
        except Exception as e:
            logger.error(f"[gallery] Error checking status for {artwork['id']}: {e}")
            pass

    completed = await repo.get_all_completed()
    return [
        GalleryItem(id=a["id"], video_url=a["video_url"], image_path=a["image_path"], facing_direction=a["facing_direction"])
        for a in completed
    ]


@app.get("/api/health")
async def health():
    return {"status": "ok"}


# ── Cloudflare Worker Entrypoint (Fallback) ───────────────────────────────────

from workers import WorkerEntrypoint

class Default(WorkerEntrypoint):
    async def fetch(self, request):
        import asgi
        return await asgi.fetch(app, request, self.env)
