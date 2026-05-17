from __future__ import annotations
import base64
import uuid
import logging
import os
from typing import List

from fastapi import FastAPI, Depends, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.db.repository import ArtworkRepository
from app.providers import AIProvider, MockProvider, GeminiVeoProvider, ProviderStatus
from app.schemas import UploadRequest, UploadResponse, GalleryItem
from app.core.config import Settings
from app.interfaces.storage import CloudflareR2Storage
from app.interfaces.http_client import JsFetchClient

class ConsoleHandler(logging.Handler):
    def emit(self, record):
        try:
            import js
            msg = self.format(record)
            if record.levelno >= logging.ERROR:
                js.console.error(msg)
            elif record.levelno >= logging.WARNING:
                js.console.warn(msg)
            else:
                js.console.log(msg)
        except:
            import sys
            print(self.format(record), file=sys.stderr)

handler = ConsoleHandler()
handler.setFormatter(logging.Formatter("[%(levelname)s] %(name)s: %(message)s"))
logging.getLogger().addHandler(handler)
logging.getLogger().setLevel(logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Paper Spells API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Internal error: {type(exc).__name__}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected internal server error occurred."}
    )

# Provider map
_provider_map: dict[str, type[AIProvider]] = {
    "gemini": GeminiVeoProvider,
    "mock": MockProvider,
}


# ── Dependencies ─────────────────────────────────────────────────────────────

async def get_repo(request: Request) -> ArtworkRepository:
    # Running on Cloudflare Workers — use the real D1 binding
    if "env" in request.scope and hasattr(request.scope["env"], "DB"):
        return ArtworkRepository(request.scope["env"].DB)
    raise HTTPException(status_code=500, detail="D1 database binding not available")

async def get_settings(request: Request) -> Settings:
    env = request.scope.get("env", None)
    return Settings.from_env(env)

async def get_provider(request: Request, settings: Settings = Depends(get_settings)) -> AIProvider:
    env = request.scope.get("env", None)
    http_client = JsFetchClient()
    storage = CloudflareR2Storage(env.BUCKET) if env and hasattr(env, "BUCKET") else None
    
    if settings.ai_provider == "gemini":
        return GeminiVeoProvider(settings=settings, http_client=http_client, storage=storage)
    return MockProvider()


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
    artwork = await repo.create_artwork(image_path=f"images/{file_id}.png", room_id=req.room_id)

    try:
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


@app.get("/api/gallery")
async def get_gallery(
    request: Request,
    room_id: str = "default",
    repo: ArtworkRepository = Depends(get_repo),
    provider: AIProvider = Depends(get_provider),
) -> List[GalleryItem]:
    generating = await repo.get_all_generating(room_id)
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

    completed = await repo.get_all_completed(room_id)
    return [
        GalleryItem(
            id=a["id"],
            video_url=a["video_url"],
            image_path=a["image_path"],
            facing_direction=a["facing_direction"]
        )
        for a in completed
    ]


@app.get("/api/health")
async def health():
    return {"status": "ok"}


# ── Cloudflare Worker Entrypoint ──────────────────────────────────────────────

from workers import WorkerEntrypoint

class Default(WorkerEntrypoint):
    async def fetch(self, request):
        import asgi
        return await asgi.fetch(app, request.js_object, self.env)