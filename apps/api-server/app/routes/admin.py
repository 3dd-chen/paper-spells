from __future__ import annotations
import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from app.schemas import AdminLoginRequest, RegenerateRequest
from app.dependencies import get_admin_repo, get_repo, get_settings, get_provider, require_admin
from app.db.repository import AdminRepository, ArtworkRepository
from app.providers import AIProvider
from app.core.config import Settings
from app.auth import create_token
from app.interfaces.storage import CloudflareR2Storage
from app.utils import get_png_ratio

logger = logging.getLogger("paper_spells.routes.admin")


def _r2_key(url, prefix: str):
    """Extract the R2 object key (e.g. 'images/x.png') from a stored media URL."""
    if not isinstance(url, str):
        return None
    idx = url.find(prefix)
    return url[idx:] if idx != -1 else None

router = APIRouter(prefix="/api/admin", tags=["Admin"])


@router.post("/login")
async def admin_login(
    req: AdminLoginRequest,
    admin_repo: AdminRepository = Depends(get_admin_repo),
    settings: Settings = Depends(get_settings),
):
    admin = await admin_repo.verify_credentials(req.username, req.password)
    if not admin:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = create_token(admin["id"], settings.jwt_secret)
    return {"token": token, "username": admin["username"]}


@router.post("/logout")
async def admin_logout(_: dict = Depends(require_admin)):
    return {"message": "Logged out"}


@router.get("/rooms")
async def admin_list_rooms(
    repo: ArtworkRepository = Depends(get_repo),
    _: dict = Depends(require_admin),
):
    rooms = await repo.get_all_rooms()
    return rooms


@router.get("/rooms/{room_id}")
async def admin_get_room_artworks(
    room_id: str,
    repo: ArtworkRepository = Depends(get_repo),
    _: dict = Depends(require_admin),
):
    artworks = await repo.get_artworks_by_room(room_id=room_id)
    return artworks


@router.post("/artworks/{artwork_id}/hide")
@router.patch("/artworks/{artwork_id}/hide")
async def admin_hide_artwork(
    artwork_id: str,
    repo: ArtworkRepository = Depends(get_repo),
    _: dict = Depends(require_admin),
):
    ok = await repo.set_hidden(artwork_id, True)
    if not ok:
        raise HTTPException(status_code=404, detail="Artwork not found")
    return {"message": "Artwork hidden"}


@router.post("/artworks/{artwork_id}/unhide")
@router.patch("/artworks/{artwork_id}/unhide")
async def admin_unhide_artwork(
    artwork_id: str,
    repo: ArtworkRepository = Depends(get_repo),
    _: dict = Depends(require_admin),
):
    ok = await repo.set_hidden(artwork_id, False)
    if not ok:
        raise HTTPException(status_code=404, detail="Artwork not found")
    return {"message": "Artwork unhidden"}


@router.post("/artworks/{artwork_id}/regenerate")
async def admin_regenerate_artwork(
    artwork_id: str,
    req: RegenerateRequest = RegenerateRequest(type="full"),
    request: Request = None,
    repo: ArtworkRepository = Depends(get_repo),
    provider: AIProvider = Depends(get_provider),
    settings: Settings = Depends(get_settings),
    _: dict = Depends(require_admin),
):
    artwork = await repo.get_by_id(artwork_id)
    if not artwork:
        raise HTTPException(status_code=404, detail="Artwork not found")

    env = request.scope.get("env", None) if request else None
    if not env or not hasattr(env, "BUCKET"):
        raise HTTPException(status_code=500, detail="R2 storage binding not found")
    storage = CloudflareR2Storage(env.BUCKET)

    # Read the original drawing straight from R2. Stored URLs may lack a scheme
    # or use an older public domain, so locate the object key by its prefix.
    original_key = _r2_key(artwork.get("image_path"), "images/")
    if not original_key:
        raise HTTPException(status_code=400, detail="Artwork has no valid image_path")
    try:
        original_bytes = await storage.download_bytes(original_key)
    except Exception as exc:
        logger.error(f"Regenerate: failed to download original image {original_key}: {exc}")
        raise HTTPException(status_code=500, detail=f"Failed to read source image from storage: {exc}")

    aspect_ratio = get_png_ratio(original_bytes)
    facing_direction = artwork.get("facing_direction")
    helmet_image_path = artwork.get("helmet_image_path")
    old_video_key = _r2_key(artwork.get("video_url"), "videos/")

    regen_type = req.type
    helmet_key = _r2_key(helmet_image_path, "images/") if regen_type == "video" else None
    helmet_bytes = None
    if regen_type == "video":
        if not hasattr(provider, "_submit_to_veo"):
            regen_type = "full"  # e.g. MockProvider has no separate video stage
        elif not helmet_key:
            logger.info("Regenerate: no helmet image for video-only regen, falling back to full")
            regen_type = "full"
        else:
            try:
                helmet_bytes = await storage.download_bytes(helmet_key)
            except Exception as exc:
                logger.warning(f"Regenerate: failed to read helmet image {helmet_key}, falling back to full: {exc}")
                regen_type = "full"

    try:
        if regen_type == "full":
            # Stage 1 + 2: new helmet image, then a new video.
            old_helmet_key = _r2_key(helmet_image_path, "images/")
            for key in (old_helmet_key, old_video_key):
                if key:
                    await storage.delete(key)

            provider_task_id, facing_direction, helmet_image_path = await provider.submit(
                image_bytes=original_bytes,
                file_id=artwork_id,
                aspect_ratio=aspect_ratio,
                env=env,
                original_direction=facing_direction,
            )
        else:
            # Stage 2 only: send the existing helmet image straight to Veo.
            # provider.submit() would rerun the helmet step on top of the helmet.
            if old_video_key:
                await storage.delete(old_video_key)
            helmet_mime = "image/jpeg" if helmet_key.lower().endswith((".jpg", ".jpeg")) else "image/png"
            prompt = (
                "a simple black stick figure wearing its glass space helmet, "
                "glowing neon outline style, "
                "walking forward naturally on a solid green background"
            )
            provider_task_id = await provider._submit_to_veo(
                custom_prompt=prompt,
                image_bytes=helmet_bytes,
                image_mime_type=helmet_mime,
                project_id=settings.gcp_project_id,
                aspect_ratio=aspect_ratio,
                file_id=artwork_id,
                env=env,
            )

        await repo.update_to_generating(
            artwork_id, provider_task_id, facing_direction, helmet_image_path, clear_video=True
        )
    except Exception as exc:
        logger.error(f"Regenerate failed for artwork {artwork_id}: {exc}")
        await repo.update_to_failed(artwork_id)
        raise HTTPException(status_code=502, detail=f"Regeneration failed: {exc}")

    return {
        "task_id": artwork_id,
        "status": "generating",
        "provider_task_id": provider_task_id,
        "type": regen_type,
    }


@router.post("/artworks/{artwork_id}/delete")
@router.delete("/artworks/{artwork_id}")
async def admin_delete_artwork(
    artwork_id: str,
    request: Request,
    repo: ArtworkRepository = Depends(get_repo),
    settings: Settings = Depends(get_settings),
    _: dict = Depends(require_admin),
):
    artwork = await repo.delete_artwork(artwork_id)
    if not artwork:
        raise HTTPException(status_code=404, detail="Artwork not found")

    env = request.scope.get("env", None)

    # Delete storage objects in Cloudflare R2
    if env and hasattr(env, "BUCKET"):
        try:
            base_url = settings.r2_public_url.rstrip("/") + "/"
            for key in ["image_path", "helmet_image_path", "video_url"]:
                url = artwork.get(key)
                if url and url.startswith(base_url):
                    object_name = url[len(base_url):]
                    if object_name:
                        await env.BUCKET.delete(object_name)
                        logger.info(f"Deleted R2 object: {object_name}")
        except Exception as exc:
            logger.error(f"Failed deleting R2 assets for artwork {artwork_id}: {exc}")

    return {"message": "Artwork deleted"}
