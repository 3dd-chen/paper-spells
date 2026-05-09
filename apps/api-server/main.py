from __future__ import annotations
import os
import base64
import uuid
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from database import engine, Base, get_db
from repository import ArtworkRepository
from provider import MockProvider, AIProvider, ProviderStatus

app = FastAPI(title="Paper Spells API")

# CORS — allow frontend dev servers
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Uploads directory
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# AI Provider (swap MockProvider for a real one later)
ai_provider: AIProvider = MockProvider()


# Setup DB on startup
@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# Pydantic Schemas
class UploadRequest(BaseModel):
    image_data: str  # Base64-encoded image


class UploadResponse(BaseModel):
    task_id: str
    status: str


class GalleryItem(BaseModel):
    id: str
    video_url: Optional[str] = None
    image_path: Optional[str] = None


# Dependency
def get_artwork_repo(db: AsyncSession = Depends(get_db)) -> ArtworkRepository:
    return ArtworkRepository(db)


# ── Endpoints ──────────────────────────────────────────────


@app.post("/api/upload", response_model=UploadResponse)
async def upload_artwork(
    req: UploadRequest,
    repo: ArtworkRepository = Depends(get_artwork_repo),
):
    """
    1. Validate and decode Base64 image
    2. Save image to disk
    3. Write DB -> pending
    4. Call Provider -> get provider_task_id
    5. Update DB -> generating
    6. Return task_id
    """
    # Step 1: Validate Base64 before any DB writes to avoid orphan records
    try:
        image_bytes = base64.b64decode(req.image_data.split(",")[-1])
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid Base64 image data")

    # Step 2: Write file to disk
    filename = f"{uuid.uuid4()}.png"
    filepath = os.path.join(UPLOAD_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(image_bytes)

    # Step 3: DB record only created after file is safely on disk
    artwork = await repo.create_artwork(image_path=filepath)

    # Step 4 & 5: Call Provider and update DB
    try:
        provider_task_id = await ai_provider.submit(filepath)
        await repo.update_to_generating(artwork.id, provider_task_id)
        return UploadResponse(task_id=artwork.id, status="generating")
    except Exception as e:
        await repo.update_to_failed(artwork.id)
        raise HTTPException(status_code=502, detail=f"Provider error: {e}")


@app.get("/api/gallery", response_model=List[GalleryItem])
async def get_gallery(
    repo: ArtworkRepository = Depends(get_artwork_repo),
):
    """
    1. Check all 'generating' tasks against Provider
    2. Update any that are done
    3. Return all 'completed' artworks
    """
    # Lazy poll: check generating tasks
    generating = await repo.get_all_generating()
    for artwork in generating:
        if not artwork.provider_task_id:
            continue
        try:
            result = await ai_provider.check_status(artwork.provider_task_id)
            if result.status == ProviderStatus.COMPLETED and result.video_url:
                await repo.update_to_completed(artwork.id, result.video_url)
            elif result.status == ProviderStatus.FAILED:
                await repo.update_to_failed(artwork.id)
        except Exception:
            pass  # Skip failed checks, retry on next gallery request

    # Return all completed
    completed = await repo.get_all_completed()
    return [
        GalleryItem(id=a.id, video_url=a.video_url, image_path=a.image_path)
        for a in completed
    ]


@app.get("/api/health")
async def health():
    return {"status": "ok"}
