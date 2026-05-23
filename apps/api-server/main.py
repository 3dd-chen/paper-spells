from __future__ import annotations
import base64
import uuid
import logging
import os
from typing import List

from fastapi import FastAPI, Depends, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.db.repository import ArtworkRepository, AdminRepository
from app.providers import AIProvider, MockProvider, GeminiVeoProvider, ProviderStatus
from app.schemas import (
    UploadRequest, UploadResponse, GalleryItem,
    AnalyzeDirectionRequest, AnalyzeDirectionResponse,
    AdminLoginRequest, AdminLoginResponse, AdminArtworkItem, AdminRoomItem,
)
from app.core.config import Settings
from app.interfaces.storage import CloudflareR2Storage
from app.interfaces.http_client import JsFetchClient
from app.auth import create_token, verify_token

class ConsoleHandler(logging.Handler):
    def emit(self, record):
        try:
            import js
            msg = self.format(record)
            if record.levelno >= logging.ERROR:
                js.console.error(msg)
            elif record.levelno >= logging.WARNING:
                js.console.warn(msg)
            elif record.levelno >= logging.INFO:
                js.console.info(msg)
            else:
                js.console.log(msg)
        except:
            import sys
            print(self.format(record), file=sys.stderr)

handler = ConsoleHandler()
handler.setFormatter(logging.Formatter("%(name)s: %(message)s")) # Remove manually duplicated [%(levelname)s] since CF dashboard already has a Level column
logging.getLogger().addHandler(handler)
logging.getLogger().setLevel(logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Paper Spells API")

# CORS origins are static by necessity: Cloudflare Python Workers deliver
# `[vars]` per-request via the ASGI scope, so no env is available at module
# import time when the middleware is registered. Edit this list to change origins.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://gallery.hissnake.com",
        "https://upload.hissnake.com",
        "http://localhost:5173",
        "http://localhost:4173",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

@app.middleware("http")
async def log_request_response(request: Request, call_next):
    method = request.method
    path = request.url.path
    query = request.url.query
    query_str = f"?{query}" if query else ""
    
    # 1. Parse Request Body safely
    body_summary = ""
    if method in ("POST", "PUT", "PATCH"):
        try:
            body_bytes = await request.body()
            
            # Restore body for downstream handlers
            async def receive():
                return {"type": "http.request", "body": body_bytes, "more_body": False}
            request._receive = receive
            
            if body_bytes:
                import json
                try:
                    body_json = json.loads(body_bytes.decode("utf-8"))
                    if isinstance(body_json, dict):
                        logged_body = body_json.copy()
                        if "image_data" in logged_body:
                            img_len = len(str(logged_body["image_data"]))
                            logged_body["image_data"] = f"<Base64 Image: {img_len} chars>"
                        body_summary = f" body={json.dumps(logged_body)}"
                    else:
                        body_summary = f" body={body_json}"
                except json.JSONDecodeError:
                    body_summary = f" body=<{len(body_bytes)} bytes>"
        except Exception as e:
            body_summary = f" body=<failed to read: {e}>"

    logger.info(f"--> {method} {path}{query_str}{body_summary}")

    # 2. Proceed to next handler
    try:
        response = await call_next(request)
    except Exception as e:
        logger.error(f"Request failed: {method} {path}{query_str}: {e}")
        raise e

    # 3. Parse Response Body safely
    resp_summary = ""
    try:
        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type or "text/" in content_type:
            chunks = []
            async for chunk in response.body_iterator:
                chunks.append(chunk)
            response_body = b"".join(chunks)
            
            # Recreate iterator so the client still gets the response
            async def new_iterator():
                for chunk in chunks:
                    yield chunk
            response.body_iterator = new_iterator()
            
            if response_body:
                import json
                try:
                    resp_json = json.loads(response_body.decode("utf-8"))
                    resp_summary = f" body={json.dumps(resp_json)}"
                except json.JSONDecodeError:
                    if len(response_body) < 500:
                        resp_summary = f" body={response_body.decode('utf-8', errors='ignore')}"
                    else:
                        resp_summary = f" body=<{len(response_body)} bytes>"
        else:
            resp_summary = f" content_type={content_type}"
    except Exception as e:
        resp_summary = f" body=<failed to read response: {e}>"

    logger.info(f"<-- {response.status_code} {method} {path} {resp_summary}")
    return response

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

async def get_admin_repo(request: Request) -> AdminRepository:
    if "env" in request.scope and hasattr(request.scope["env"], "DB"):
        return AdminRepository(request.scope["env"].DB)
    raise HTTPException(status_code=500, detail="D1 database binding not available")

async def require_admin(request: Request, settings: Settings = Depends(get_settings)):
    auth = request.headers.get("Authorization", "")
    token = auth.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")
    return verify_token(token, settings.jwt_secret)


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
    r2_public_url = (await get_settings(request)).r2_public_url.rstrip("/")
    artwork = await repo.create_artwork(image_path=f"{r2_public_url}/images/{file_id}.png", room_id=req.room_id)

    try:
        env = request.scope.get("env", None)
        provider_task_id, facing_direction = await provider.submit(
            image_bytes=image_bytes,
            file_id=file_id,
            aspect_ratio=req.aspect_ratio,
            env=env,
            original_direction=req.original_direction
        )
        logger.info(f"Provider accepted task: {provider_task_id}, direction: {facing_direction}")
        await repo.update_to_generating(artwork["id"], provider_task_id, facing_direction)
        return UploadResponse(task_id=artwork["id"], status="generating")
    except Exception as e:
        logger.error(f"Provider error for artwork {artwork['id']}: {type(e).__name__}: {e}")
        await repo.update_to_failed(artwork["id"])
        raise HTTPException(status_code=502, detail=f"Provider error: {type(e).__name__}: {e}")


@app.post("/api/analyze-direction", response_model=AnalyzeDirectionResponse)
async def analyze_direction(
    req: AnalyzeDirectionRequest,
    request: Request,
    provider: AIProvider = Depends(get_provider),
) -> AnalyzeDirectionResponse:
    try:
        image_bytes = base64.b64decode(req.image_data.split(",")[-1])
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid Base64 image data")

    if not isinstance(provider, GeminiVeoProvider):
        return AnalyzeDirectionResponse(direction="right")

    env = request.scope.get("env", None)
    direction = await provider.analyze_image_direction(image_bytes, env=env)
    return AnalyzeDirectionResponse(direction=direction)


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
                await repo.update_to_completed(artwork["id"], result.video_url, result.facing_direction)
            elif result.status == ProviderStatus.FAILED:
                await repo.update_to_failed(artwork["id"])
        except Exception as e:
            logger.error(f"Error checking status for {artwork['id']}: {e}")

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


# ── Admin Routes ─────────────────────────────────────────────────────────────

@app.post("/api/admin/login", response_model=AdminLoginResponse)
async def admin_login(
    req: AdminLoginRequest,
    admin_repo: AdminRepository = Depends(get_admin_repo),
    settings: Settings = Depends(get_settings),
):
    import time
    admin = await admin_repo.verify_credentials(req.username, req.password)
    if not admin:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    expires_in = 86400  # 24 hours
    token = create_token(admin["id"], settings.jwt_secret, expires_in)
    return AdminLoginResponse(token=token, expires_at=int(time.time()) + expires_in)


@app.post("/api/admin/logout")
async def admin_logout(_=Depends(require_admin)):
    return {"status": "ok"}


@app.get("/api/admin/rooms", response_model=list[AdminRoomItem])
async def admin_list_rooms(
    repo: ArtworkRepository = Depends(get_repo),
    _=Depends(require_admin),
):
    rooms = await repo.get_all_rooms()
    return [AdminRoomItem(**r) for r in rooms]


@app.get("/api/admin/rooms/{room_id}", response_model=list[AdminArtworkItem])
async def admin_get_room(
    room_id: str,
    repo: ArtworkRepository = Depends(get_repo),
    _=Depends(require_admin),
):
    artworks = await repo.get_artworks_by_room(room_id)
    def to_item(a: dict) -> AdminArtworkItem:
        # D1 NULL values may not come back as Python None in Pydantic v1 — coerce explicitly
        return AdminArtworkItem(
            id=str(a.get("id", "")),
            room_id=str(a.get("room_id", "")),
            status=str(a.get("status", "")),
            hidden=int(a.get("hidden") or 0),
            video_url=str(a["video_url"]) if a.get("video_url") else None,
            image_path=str(a["image_path"]) if a.get("image_path") else None,
            facing_direction=str(a["facing_direction"]) if a.get("facing_direction") else None,
            created_at=str(a["created_at"]) if a.get("created_at") else None,
        )
    return [to_item(a) for a in artworks]


@app.post("/api/admin/artworks/{artwork_id}/hide")
@app.patch("/api/admin/artworks/{artwork_id}/hide")
async def admin_hide_artwork(
    artwork_id: str,
    repo: ArtworkRepository = Depends(get_repo),
    _=Depends(require_admin),
):
    await repo.set_hidden(artwork_id, True)
    return {"status": "hidden"}


@app.post("/api/admin/artworks/{artwork_id}/unhide")
@app.patch("/api/admin/artworks/{artwork_id}/unhide")
async def admin_unhide_artwork(
    artwork_id: str,
    repo: ArtworkRepository = Depends(get_repo),
    _=Depends(require_admin),
):
    await repo.set_hidden(artwork_id, False)
    return {"status": "visible"}


@app.post("/api/admin/artworks/{artwork_id}/delete")
@app.delete("/api/admin/artworks/{artwork_id}")
async def admin_delete_artwork(
    artwork_id: str,
    request: Request,
    repo: ArtworkRepository = Depends(get_repo),
    _=Depends(require_admin),
):
    artwork = await repo.delete_artwork(artwork_id)
    if not artwork:
        raise HTTPException(status_code=404, detail="Artwork not found")

    # Clean up R2 files
    env = request.scope.get("env", None)
    if env and hasattr(env, "BUCKET"):
        storage = CloudflareR2Storage(env.BUCKET)
        for key in [artwork.get("image_path"), artwork.get("video_url")]:
            if key:
                # Extract correct R2 key (e.g. 'images/...' or 'videos/...') from full URL or domain prefix
                for prefix in ["images/", "videos/"]:
                    idx = key.find(prefix)
                    if idx != -1:
                        key = key[idx:]
                        break
                try:
                    await storage.delete(key)
                except Exception as e:
                    logger.warning(f"[admin] Failed to delete R2 key {key}: {e}")

    return {"status": "deleted"}


# ── Cloudflare Worker Entrypoint ──────────────────────────────────────────────

from workers import WorkerEntrypoint

class Default(WorkerEntrypoint):
    async def fetch(self, request):
        import asgi
        return await asgi.fetch(app, request.js_object, self.env)