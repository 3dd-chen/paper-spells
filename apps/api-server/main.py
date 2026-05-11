from __future__ import annotations
import base64
import uuid
import logging
from typing import List

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from app.config import AI_PROVIDER, UPLOAD_DIR
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
    allow_origins=["http://localhost:5173", "http://localhost:5174"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Select provider based on AI_PROVIDER env var
_provider_map: dict[str, type[AIProvider]] = {
    "gemini": GeminiVeoProvider,
    "mock": MockProvider,
}
ai_provider: AIProvider = _provider_map.get(AI_PROVIDER, MockProvider)()


# ── Dependency ────────────────────────────────────────────────────────────────

def get_repo(request: Request) -> ArtworkRepository:
    # Access the D1 binding from the request scope env (provided by Cloudflare)
    db = request.scope["env"].DB
    return ArtworkRepository(db)


# ── Routes ───────────────────────────────────────────────────────────────────

@app.post("/api/upload", response_model=UploadResponse)
async def upload_artwork(
    req: UploadRequest,
    request: Request,
    repo: ArtworkRepository = Depends(get_repo),
) -> UploadResponse:
    """
    1. Validate + decode Base64 image
    2. Save image to disk
    3. Write DB record (pending)
    4. Submit to AI provider → get provider_task_id
    5. Update DB record (generating)
    6. Return task_id to client
    """
    # Step 1: Validate Base64 before any DB writes
    try:
        image_bytes = base64.b64decode(req.image_data.split(",")[-1])
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid Base64 image data")

    # Step 2: Write file to disk (UPLOAD_DIR is resolved from config.py)
    filename = f"{uuid.uuid4()}.png"
    filepath = UPLOAD_DIR / filename
    filepath.write_bytes(image_bytes)

    # Step 3: DB record — only created after file is safely written
    artwork = await repo.create_artwork(image_path=str(filepath))

    # Steps 4 & 5
    try:
        r2_bucket = request.scope["env"].BUCKET
        provider_task_id, facing_direction = await ai_provider.submit(str(filepath), req.aspect_ratio, r2_bucket=r2_bucket)
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
) -> List[GalleryItem]:
    """
    Lazy-poll all 'generating' tasks, update completed/failed ones,
    then return all completed artworks.
    """
    generating = await repo.get_all_generating()
    r2_bucket = request.scope["env"].BUCKET
    
    for artwork in generating:
        if not artwork["provider_task_id"]:
            continue
        try:
            result = await ai_provider.check_status(artwork["provider_task_id"], r2_bucket=r2_bucket)
            if result.status == ProviderStatus.COMPLETED and result.video_url:
                await repo.update_to_completed(artwork["id"], result.video_url)
            elif result.status == ProviderStatus.FAILED:
                await repo.update_to_failed(artwork["id"])
        except Exception:
            pass  # Retry on next gallery poll

    completed = await repo.get_all_completed()
    return [
        GalleryItem(id=a["id"], video_url=a["video_url"], image_path=a["image_path"], facing_direction=a["facing_direction"])
        for a in completed
    ]


@app.get("/api/health")
async def health():
    return {"status": "ok"}


# ── Cloudflare Worker Entrypoint ─────────────────────────────────────────────

from workers import WorkerEntrypoint

class Default(WorkerEntrypoint):
    async def fetch(self, request):
        import asgi
        return await asgi.fetch(app, request, self.env)
