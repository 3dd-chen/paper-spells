from __future__ import annotations
import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from app.schemas import AdminLoginRequest, RegenerateRequest
from app.dependencies import get_admin_repo, get_repo, get_settings, get_provider, require_admin
from app.db.repository import AdminRepository, ArtworkRepository
from app.providers import AIProvider
from app.core.config import Settings
from app.auth import create_token
from app.interfaces.http_client import JsFetchClient

logger = logging.getLogger("paper_spells.routes.admin")

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
    token = create_token(admin["id"], admin["username"], settings.jwt_secret)
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

    # Fetch original image bytes
    original_image_url = artwork["image_path"]
    try:
        http_client = JsFetchClient()
        image_bytes = await http_client.get_bytes(original_image_url)
    except Exception as exc:
        logger.error(f"Failed to fetch original image from {original_image_url}: {exc}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch original image: {exc}")

    if req.type == "video" and artwork.get("helmet_image_path"):
        # Video-only regeneration: Reuse existing helmet image
        helmet_url = artwork["helmet_image_path"]
        try:
            helmet_bytes = await http_client.get_bytes(helmet_url)
            # Submit to Veo directly with helmet image
            veo_res = await provider.submit(
                image_bytes=helmet_bytes,
                file_id=artwork_id,
                env=env,
                original_direction=artwork.get("facing_direction")
            )
            provider_task_id = veo_res[0]
            facing_dir = veo_res[1]
            await repo.update_to_generating(artwork_id, provider_task_id, facing_dir, helmet_url)
            return {"task_id": artwork_id, "status": "generating", "type": "video"}
        except Exception as exc:
            logger.warning(f"Failed to reuse helmet image for video regen, falling back to full regen: {exc}")

    # Full regeneration: Run full pipeline (helmet + video)
    try:
        provider_task_id, facing_direction, helmet_image_path = await provider.submit(
            image_bytes=image_bytes,
            file_id=artwork_id,
            env=env,
            original_direction=artwork.get("facing_direction")
        )
        await repo.update_to_generating(artwork_id, provider_task_id, facing_direction, helmet_image_path)
    except Exception as exc:
        logger.error(f"Regeneration provider error for artwork {artwork_id}: {exc}")
        await repo.update_to_failed(artwork_id)
        raise HTTPException(status_code=502, detail=f"Regeneration provider error: {exc}")

    return {
        "task_id": artwork_id,
        "status": "generating",
        "type": "full"
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
