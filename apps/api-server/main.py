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
    RegenerateRequest,
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

from starlette.types import ASGIApp, Scope, Receive, Send

class LoggingASGIMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope["method"]
        path = scope["path"]

        # Block common vulnerability scanners (/.env, /.git, /wp-admin, etc.)
        path_lower = path.lower()
        scanner_keywords = {
            ".env", ".git", "wp-admin", "wordpress", "phpmyadmin",
            "xmlrpc", "cgi-bin", "config.php", "setup.php", "backup"
        }
        if any(kw in path_lower for kw in scanner_keywords):
            logger.warning(f"Blocked scanner request: {method} {path}")
            await send({
                "type": "http.response.start",
                "status": 403,
                "headers": [
                    (b"content-type", b"application/json"),
                ]
            })
            await send({
                "type": "http.response.body",
                "body": b'{"detail":"Access denied"}'
            })
            return

        query = scope["query_string"].decode("utf-8")
        query_str = f"?{query}" if query else ""

        # 1. Capture request body safely
        body_chunks = []
        async def receive_wrapper():
            message = await receive()
            if message["type"] == "http.request":
                body_chunks.append(message.get("body", b""))
            return message

        # 2. Capture response body safely
        response_chunks = []
        status_code = [200]
        content_type = [""]

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status_code[0] = message["status"]
                for name, val in message.get("headers", []):
                    if name.lower() == b"content-type":
                        content_type[0] = val.decode("utf-8")
                        break
            elif message["type"] == "http.response.body":
                response_chunks.append(message.get("body", b""))
            await send(message)

        # Call next ASGI handler (FastAPI / Router / CORSMiddleware)
        try:
            await self.app(scope, receive_wrapper, send_wrapper)
        except Exception as e:
            logger.error(f"Request failed: {method} {path}{query_str}: {e}")
            raise e

        # 3. Log request and response post-execution!
        request_body = b"".join(body_chunks)
        response_body = b"".join(response_chunks)

        body_summary = ""
        if request_body:
            import json
            try:
                body_json = json.loads(request_body.decode("utf-8"))
                if isinstance(body_json, dict):
                    logged_body = body_json.copy()
                    if "image_data" in logged_body:
                        img_len = len(str(logged_body["image_data"]))
                        logged_body["image_data"] = f"<Base64 Image: {img_len} chars>"
                    body_summary = f" body={json.dumps(logged_body)}"
                else:
                    body_summary = f" body={body_json}"
            except Exception:
                if len(request_body) > 1000:
                    body_summary = f" body=<{len(request_body)} bytes>"
                else:
                    body_summary = f" body={request_body.decode('utf-8', errors='ignore')}"

        logger.info(f"--> {method} {path}{query_str}{body_summary}")

        resp_summary = ""
        if response_body and ("application/json" in content_type[0] or "text/" in content_type[0]):
            import json
            try:
                resp_json = json.loads(response_body.decode("utf-8"))
                resp_summary = f" body={json.dumps(resp_json)}"
            except Exception:
                if len(response_body) < 500:
                    resp_summary = f" body={response_body.decode('utf-8', errors='ignore')}"
                else:
                    resp_summary = f" body=<{len(response_body)} bytes>"
        else:
            resp_summary = f" content_type={content_type[0]}"

        logger.info(f"<-- {status_code[0]} {method} {path} {resp_summary}")

app = FastAPI(title="Paper Spells API")

# Register middlewares in reverse order (LIFO).
# Adding LoggingASGIMiddleware first and CORSMiddleware second means CORSMiddleware 
# runs first, handling CORS preflights before passing to LoggingASGIMiddleware.
app.add_middleware(LoggingASGIMiddleware)

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
        provider_task_id, facing_direction, helmet_image_path = await provider.submit(
            image_bytes=image_bytes,
            file_id=file_id,
            aspect_ratio=req.aspect_ratio,
            env=env,
            original_direction=req.original_direction,
            character_description=req.character_description
        )
        logger.info(f"Provider accepted task: {provider_task_id}, direction: {facing_direction}")
        await repo.update_to_generating(artwork["id"], provider_task_id, facing_direction, helmet_image_path)
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
        return AnalyzeDirectionResponse(direction="right", description="a simple black stick figure")

    env = request.scope.get("env", None)
    result = await provider.analyze_image_direction(image_bytes, env=env)
    return AnalyzeDirectionResponse(direction=result["direction"], description=result["description"])


@app.get("/api/gallery")
async def get_gallery(
    request: Request,
    room_id: str = "default",
    repo: ArtworkRepository = Depends(get_repo),
) -> List[GalleryItem]:
    """Return only completed artworks. Fast DB-only read — no external calls."""
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


@app.post("/api/poll")
async def poll_generating(
    request: Request,
    room_id: str = "default",
    repo: ArtworkRepository = Depends(get_repo),
    provider: AIProvider = Depends(get_provider),
):
    """Check Veo status for generating artworks and update DB.
    1. First batch-cleanup any stuck task older than 15 minutes.
    2. Limits subrequests by checking at most 5 generating tasks per poll.
    """
    # Auto-fail stuck tasks older than 15 minutes in one query
    cleaned_count = await repo.cleanup_stuck_artworks(room_id, timeout_minutes=15)
    if cleaned_count > 0:
        logger.info(f"Cleaned up {cleaned_count} stuck generating tasks to failed status.")

    # Limit to checking 5 tasks to respect Worker subrequest bounds (max 10 on Free)
    generating = await repo.get_all_generating(room_id, limit=5)
    env = request.scope.get("env", None)
    updated = []

    for artwork in generating:
        if not artwork["provider_task_id"]:
            continue
        try:
            result = await provider.check_status(artwork["provider_task_id"], env=env)
            if result.status == ProviderStatus.COMPLETED and result.video_url:
                await repo.update_to_completed(artwork["id"], result.video_url, result.facing_direction)
                updated.append({"id": artwork["id"], "status": "completed"})
            elif result.status == ProviderStatus.FAILED:
                await repo.update_to_failed(artwork["id"])
                updated.append({"id": artwork["id"], "status": "failed"})
            else:
                updated.append({"id": artwork["id"], "status": "generating"})
        except Exception as e:
            logger.error(f"poll: error checking status for {artwork['id']}: {e}")
            updated.append({"id": artwork["id"], "status": "error", "error": str(e)})

    return {
        "checked": len(updated),
        "results": updated,
        "auto_failed_stuck": cleaned_count
    }


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/debug-status")
async def debug_status(
    task_id: str,
    request: Request,
    provider: AIProvider = Depends(get_provider),
):
    if not isinstance(provider, GeminiVeoProvider):
        return {"error": "Not a Gemini provider"}
    
    from app.providers.gcp_auth import get_access_token
    import json
    
    project_id = provider.settings.gcp_project_id
    parts = task_id.rpartition('/operations/')
    resource_name = parts[0] if parts[1] else task_id
    url = f"https://{provider.settings.google_cloud_location}-aiplatform.googleapis.com/v1beta1/{resource_name}:fetchPredictOperation"
    token = await get_access_token(provider.settings, provider.http_client, provider.token_store)
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "operationName": task_id
    }
    try:
        res_json = await provider.http_client.post_json(url, headers, payload)
        return res_json
    except Exception as e:
        return {"error": str(e)}


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
    """Return all artworks in a room. Fast DB-only read — no status checking loops."""
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
            helmet_image_path=str(a["helmet_image_path"]) if a.get("helmet_image_path") else None,
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


def get_png_ratio(data: bytes) -> str:
    """Helper to detect aspect ratio from PNG binary data headers."""
    if data.startswith(b'\x89PNG\r\n\x1a\n') and len(data) >= 24:
        w = int.from_bytes(data[16:20], byteorder="big")
        h = int.from_bytes(data[20:24], byteorder="big")
        return "9:16" if h > w else "16:9"
    return "16:9"


@app.post("/api/admin/artworks/{artwork_id}/regenerate")
async def admin_regenerate_artwork(
    artwork_id: str,
    req: RegenerateRequest,
    request: Request,
    repo: ArtworkRepository = Depends(get_repo),
    provider: AIProvider = Depends(get_provider),
    _=Depends(require_admin),
):
    artwork = await repo.get_by_id(artwork_id)
    if not artwork:
        raise HTTPException(status_code=404, detail="Artwork not found")

    env = request.scope.get("env", None)
    if not env or not hasattr(env, "BUCKET"):
        raise HTTPException(status_code=500, detail="R2 storage binding not found")
    storage = CloudflareR2Storage(env.BUCKET)

    # 1. Resolve raw original image path
    image_url = artwork.get("image_path")
    if not image_url:
        raise HTTPException(status_code=400, detail="Artwork record has no image_path")
    idx = image_url.find("images/")
    if idx == -1:
        raise HTTPException(status_code=400, detail="Invalid image URL structure")
    original_image_key = image_url[idx:]

    try:
        # Download original image bytes (required for both paths)
        original_image_bytes = await storage.download_bytes(original_image_key)
    except Exception as e:
        logger.error(f"Regenerate: failed to download original image {original_image_key}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to read source image from storage: {e}")

    aspect_ratio = get_png_ratio(original_image_bytes)
    facing_direction = artwork.get("facing_direction")
    helmet_image_path = artwork.get("helmet_image_path")

    # Force fallback to full regeneration if user requested video-only but no helmet image exists
    regen_type = req.type
    if regen_type == "video" and not helmet_image_path:
        logger.info("Regenerate: video-only requested but no helmet image path exists. Falling back to full.")
        regen_type = "full"

    try:
        if regen_type == "full":
            # --- FULL REGENERATION (Stage 1 + Stage 2) ---
            # 1. Clean up old helmet file and video file from R2
            for url in [helmet_image_path, artwork.get("video_url")]:
                if url:
                    for prefix in ["images/", "videos/"]:
                        i = url.find(prefix)
                        if i != -1:
                            try:
                                await storage.delete(url[i:])
                            except Exception:
                                pass

            # 2. Run both stages synchronously
            provider_task_id, facing_direction, helmet_image_path = await provider.submit(
                image_bytes=original_image_bytes,
                file_id=artwork_id,
                aspect_ratio=aspect_ratio,
                env=env,
                original_direction=facing_direction,
                character_description=None
            )

        else:
            # --- VIDEO-ONLY REGENERATION (Stage 2 only) ---
            # 1. Download existing helmet image from R2
            idx_h = helmet_image_path.find("images/")
            if idx_h == -1:
                raise ValueError("Invalid helmet image path structure")
            helmet_key = helmet_image_path[idx_h:]
            try:
                helmet_image_bytes = await storage.download_bytes(helmet_key)
                helmet_mime_type = "image/jpeg" if helmet_key.lower().endswith((".jpg", ".jpeg")) else "image/png"
            except Exception as e:
                logger.warning(f"Regenerate: failed to read helmet image {helmet_key}, falling back to full: {e}")
                # Fallback to full generation if R2 file missing
                return await admin_regenerate_artwork(artwork_id, RegenerateRequest(type="full"), request, repo, provider)

            # 2. Clean up old video file from R2
            old_video_url = artwork.get("video_url")
            if old_video_url:
                idx_v = old_video_url.find("videos/")
                if idx_v != -1:
                    try:
                        await storage.delete(old_video_url[idx_v:])
                    except Exception:
                        pass

            # 3. Submit helmet image directly to Veo
            char_desc = "a simple black stick figure"
            custom_prompt = (
                f"{char_desc} wearing its glass space helmet, "
                "glowing neon outline style, "
                "walking forward naturally on a solid green background"
            )
            project_id = provider.settings.gcp_project_id
            provider_task_id = await provider._submit_to_veo(
                custom_prompt=custom_prompt,
                image_bytes=helmet_image_bytes,
                image_mime_type=helmet_mime_type,
                project_id=project_id,
                aspect_ratio=aspect_ratio,
                file_id=artwork_id,
                env=env
            )

        # 3. Update database status to generating and clear video_url
        await repo.update_to_generating(artwork_id, provider_task_id, facing_direction, helmet_image_path)
        await repo.db.prepare("UPDATE artworks SET video_url = NULL WHERE id = ?").bind(artwork_id).run()

        return {
            "status": "generating",
            "task_id": artwork_id,
            "provider_task_id": provider_task_id,
            "type": regen_type
        }

    except Exception as e:
        logger.error(f"Regenerate failed for artwork {artwork_id}: {e}")
        await repo.update_to_failed(artwork_id)
        raise HTTPException(status_code=502, detail=f"Regeneration failed: {e}")


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

    # Clean up R2 files (including original image, video, helmet versions, and legacy raw backups)
    env = request.scope.get("env", None)
    if env and hasattr(env, "BUCKET"):
        storage = CloudflareR2Storage(env.BUCKET)
        
        # Build collection of keys to delete
        keys_to_delete = []
        
        # Add main image and video if present in D1
        for url in [artwork.get("image_path"), artwork.get("video_url")]:
            if url:
                for prefix in ["images/", "videos/"]:
                    idx = url.find(prefix)
                    if idx != -1:
                        keys_to_delete.append(url[idx:])
                        break
                        
        # Add generated helmet variations and legacy raw paths to ensure full cleanup
        keys_to_delete.append(f"images/{artwork_id}_helmet.png")
        keys_to_delete.append(f"images/{artwork_id}_helmet.jpg")
        keys_to_delete.append(f"images/{artwork_id}_raw.png")
        
        for key in keys_to_delete:
            try:
                await storage.delete(key)
            except Exception as e:
                logger.warning(f"[admin] Failed to delete R2 key {key}: {e}")

    return {"status": "deleted"}


# ── Cloudflare Worker Entrypoint ──────────────────────────────────────────────

try:
    from workers import WorkerEntrypoint

    class Default(WorkerEntrypoint):
        async def fetch(self, request):
            import asgi
            return await asgi.fetch(app, request.js_object, self.env)
except ImportError:
    pass