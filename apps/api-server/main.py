from __future__ import annotations
import base64
import uuid
import logging
import os
from typing import List

from fastapi import FastAPI, Depends, HTTPException, Request, Response
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

@app.middleware("http")
async def add_cors_header(request: Request, call_next):
    if request.method == "OPTIONS":
        return Response(
            status_code=204,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "*",
                "Access-Control-Allow-Headers": "*",
                "Access-Control-Max-Age": "86400"
            }
        )
    
    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "*"
    return response


# Provider map
_provider_map: dict[str, type[AIProvider]] = {
    "gemini": GeminiVeoProvider,
    "mock": MockProvider,
}


# ── Dependencies ─────────────────────────────────────────────────────────────

def get_repo(request: Request) -> ArtworkRepository:
    # Running on Cloudflare Workers — use the real D1 binding
    if "env" in request.scope and hasattr(request.scope["env"], "DB"):
        return ArtworkRepository(request.scope["env"].DB)
    raise HTTPException(status_code=500, detail="D1 database binding not available")

def get_provider(request: Request) -> AIProvider:
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

    completed = await repo.get_all_completed()
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
        from js import Response as JsResponse, Headers as JsHeaders
        try:
            if request.method == "OPTIONS":
                headers = JsHeaders.new({
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                    "Access-Control-Allow-Headers": "Content-Type, Authorization",
                    "Access-Control-Max-Age": "86400",
                })
                return JsResponse.new("", status=204, headers=headers)
                
            import asgi
            resp = await asgi.fetch(app, request, self.env)
            # Force CORS header on the response
            resp.headers.set("Access-Control-Allow-Origin", "*")
            return resp
        except Exception as e:
            return JsResponse.new(f"Python Worker Error: {str(e)}", status=500)


