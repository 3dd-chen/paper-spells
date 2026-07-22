from __future__ import annotations
import base64
import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from app.schemas import UploadRequest, AnalyzeDirectionRequest
from app.dependencies import get_repo, get_settings, get_provider
from app.db.repository import ArtworkRepository
from app.providers import AIProvider, ProviderStatus
from app.core.config import Settings
from app.utils import get_png_ratio

logger = logging.getLogger("paper_spells.routes.public")

router = APIRouter(prefix="/api", tags=["Public"])


@router.get("/health")
async def health_check():
    return {"status": "ok"}


@router.post("/upload")
async def upload_artwork(
    req: UploadRequest,
    request: Request,
    repo: ArtworkRepository = Depends(get_repo),
    provider: AIProvider = Depends(get_provider),
    settings: Settings = Depends(get_settings),
):
    try:
        # Decode base64 image data
        header, b64data = req.image_data.split(",", 1) if "," in req.image_data else ("", req.image_data)
        image_bytes = base64.b64decode(b64data)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid base64 image data: {exc}")

    if not req.aspect_ratio:
        req.aspect_ratio = get_png_ratio(image_bytes)

    env = request.scope.get("env", None)
    file_id = str(uuid.uuid4())
    filename = f"{file_id}.png"

    # Save original drawing
    if env and hasattr(env, "BUCKET"):
        try:
            await env.BUCKET.put(
                filename,
                image_bytes,
                httpMetadata={"contentType": "image/png", "cacheControl": "public, max-age=2592000"}
            )
            image_url = f"{settings.r2_public_url.rstrip('/')}/{filename}"
        except Exception as exc:
            logger.error(f"R2 storage error: {exc}")
            raise HTTPException(status_code=500, detail=f"Failed to upload drawing to storage: {exc}")
    else:
        image_url = f"https://mock-storage.com/images/{filename}"

    artwork = await repo.create_artwork(
        image_path=image_url,
        room_id=req.room_id
    )

    try:
        provider_task_id, facing_direction, helmet_image_path = await provider.submit(
            image_bytes=image_bytes,
            file_id=artwork["id"],
            aspect_ratio=req.aspect_ratio,
            env=env,
            original_direction=req.original_direction,
            character_description=req.character_description
        )
        logger.info(f"Provider accepted task: {provider_task_id}, direction: {facing_direction}")

        await repo.update_to_generating(artwork["id"], provider_task_id, facing_direction, helmet_image_path)
    except Exception as exc:
        logger.error(f"Provider error for artwork {artwork['id']}: {type(exc).__name__}: {exc}")
        await repo.update_to_failed(artwork["id"])
        raise HTTPException(status_code=502, detail=f"Provider error: {type(exc).__name__}: {exc}")

    return {
        "task_id": artwork["id"],
        "status": "generating"
    }


@router.post("/analyze-direction")
async def analyze_direction(
    req: AnalyzeDirectionRequest,
    request: Request,
    provider: AIProvider = Depends(get_provider),
):
    try:
        header, b64data = req.image_data.split(",", 1) if "," in req.image_data else ("", req.image_data)
        image_bytes = base64.b64decode(b64data)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid base64 image data: {exc}")

    env = request.scope.get("env", None)
    result = await provider.analyze_image_direction(image_bytes, env=env)
    return result


@router.get("/gallery")
async def get_gallery(
    room_id: str = Query("default"),
    repo: ArtworkRepository = Depends(get_repo)
):
    artworks = await repo.get_all_completed(room_id=room_id)
    return artworks


@router.post("/poll")
async def poll_artwork_status(
    room_id: str = Query("default"),
    repo: ArtworkRepository = Depends(get_repo),
    provider: AIProvider = Depends(get_provider),
    request: Request = None,
):
    """
    Poll endpoint called periodically by the frontend.
    Checks generating artworks in DB and queries Provider for status updates.
    """
    env = request.scope.get("env", None) if request else None

    # Clean up tasks that have been generating for >15 minutes
    await repo.cleanup_stuck_artworks(room_id=room_id, timeout_minutes=15)

    pending_artworks = await repo.get_all_generating(room_id=room_id, limit=5)
    updated_count = 0

    for artwork in pending_artworks:
        task_id = artwork["id"]
        provider_task_id = artwork.get("provider_task_id")

        if not provider_task_id:
            continue

        try:
            res = await provider.check_status(provider_task_id, env=env)

            if res.status == ProviderStatus.COMPLETED and res.video_url:
                await repo.update_to_completed(task_id, res.video_url, res.facing_direction)
                updated_count += 1
                logger.info(f"Task {task_id} marked COMPLETED. Video: {res.video_url}")
            elif res.status == ProviderStatus.FAILED:
                await repo.update_to_failed(task_id)
                logger.warning(f"Task {task_id} marked FAILED.")

        except Exception as exc:
            logger.error(f"Error polling status for task {task_id}: {exc}")

    return {"polled_count": len(pending_artworks), "updated_count": updated_count}


@router.get("/debug-status")
async def debug_status(
    room_id: str = Query("default"),
    repo: ArtworkRepository = Depends(get_repo)
):
    artworks = await repo.get_artworks_by_room(room_id=room_id)
    return artworks
