"""
Google Vertex AI (REST) + Cloudflare R2 provider for Cloudflare Workers.

Features:
- Uses Gemini 2.5 Flash Lite for image analysis (Vertex AI).
- Uses Veo 3.1 Lite via `:predictLongRunning` REST endpoint (Vertex AI).
- Handles Base64 video response directly (No GCS bucket needed!).
- Compatible with Cloudflare Workers (uses env.BUCKET if available, falls back to local file for testing).
"""
from __future__ import annotations
import asyncio
import logging
import os
import base64
import json
from typing import Optional, Any
from app.providers.base import AIProvider, ProviderResult, ProviderStatus
from app.providers.gcp_auth import get_access_token
from app.core.config import Settings
from app.interfaces.http_client import HttpClientInterface
from app.interfaces.storage import StorageInterface

logger = logging.getLogger(__name__)

# HTTP statuses where the Veo operation is permanently gone/invalid and
# polling will never succeed. 429 (quota) and 408 (timeout) are deliberately
# excluded — they are transient and the generation may still be running.
_TERMINAL_HTTP_STATUSES = {400, 403, 404, 410}


def _terminal_http_status(exc_message: str) -> int | None:
    """Return the HTTP status if `exc_message` signals a non-recoverable error.

    JsFetchClient raises exceptions formatted as "HTTP <status>: <body>".
    Returns the status code only when it is a known terminal status,
    otherwise None (caller should treat as transient and retry).
    """
    if not exc_message.startswith("HTTP "):
        return None
    try:
        status_code = int(exc_message.split(" ", 2)[1].rstrip(":"))
    except (ValueError, IndexError):
        return None
    return status_code if status_code in _TERMINAL_HTTP_STATUSES else None


class GeminiVeoProvider(AIProvider):
    def __init__(self, settings: Settings, http_client: HttpClientInterface, storage: StorageInterface | None = None) -> None:
        self.settings = settings
        self.http_client = http_client
        self.storage = storage
        self.token_store = {"token": None, "expiry": 0}

    async def analyze_image_direction(self, image_bytes: bytes, env: Any = None) -> dict[str, str]:
        """Analyze the image to determine if the character is facing left or right and get a description."""
        logger.info(f"Analyzing image direction with {self.settings.gemini_model_name}")
        project_id = self.settings.gcp_project_id

        prompt_text = (
            "You are an expert at analyzing hand-drawn doodles, sketches, and characters.\n"
            "Look at the main subject/character in this image and determine:\n"
            "1. 'direction': The horizontal direction the character is facing. Is it facing the left side of the screen ('left') or the right side ('right')?\n"
            "   - Use cues like the direction of the face, beak, eyes, nose, front of a vehicle, or forward posture.\n"
            "   - If it is facing forward (towards the viewer) or direction is completely ambiguous, default to 'right'.\n"
            "2. 'description': A brief (3-6 words) description of the character itself (e.g. 'a simple drawing of a white goose', 'a black stick figure', 'a cute hand-drawn dog'). Describe ONLY the character's core shape and color. Do not describe the background, green screen, or padding.\n\n"
            "Return ONLY a valid JSON object of the format: {\"direction\": \"left\" | \"right\", \"description\": \"...\"}\n"
            "Do not include markdown code blocks (e.g., do not wrap in ```json), and do not include any other text."
        )

        try:
            api_key = self.settings.gemini_api_key

            if api_key:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.settings.gemini_model_name}:generateContent?key={api_key}"
                headers = {"Content-Type": "application/json"}
            else:
                url = f"https://{self.settings.google_cloud_location}-aiplatform.googleapis.com/v1/projects/{project_id}/locations/{self.settings.google_cloud_location}/publishers/google/models/{self.settings.gemini_model_name}:generateContent"
                token = await get_access_token(self.settings, self.http_client, self.token_store)
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {token}"
                }

            image_b64 = base64.b64encode(image_bytes).decode('utf-8')

            payload = {
                "contents": [
                    {
                        "role": "user",
                        "parts": [
                            {"inline_data": {"mime_type": "image/png", "data": image_b64}},
                            {"text": prompt_text}
                        ]
                    }
                ]
            }

            res_json = await self.http_client.post_json(url, headers, payload)
            text = res_json["candidates"][0]["content"]["parts"][0]["text"].strip()

            # Robust JSON extraction: slice out everything between first '{' and last '}'
            start = text.find('{')
            end = text.rfind('}')
            if start != -1 and end != -1 and end > start:
                json_str = text[start:end+1]
            else:
                json_str = text

            result = json.loads(json_str)
            direction = result.get("direction", "right")
            if direction not in ("left", "right"):
                direction = "right"
            description = result.get("description", "a simple black stick figure")
            return {"direction": direction, "description": description}

        except Exception as e:
            logger.warning(f"Direction analysis failed, defaulting. Error: {e}")
            return {"direction": "right", "description": "a simple black stick figure"}

    # ── submit ────────────────────────────────────────────────────────────────

    async def submit(self, image_bytes: bytes, file_id: str, aspect_ratio: str = "16:9", env: Any = None, original_direction: str | None = None, character_description: str | None = None) -> tuple[str, str | None]:
        project_id = self.settings.gcp_project_id

        # 1. Upload original image to R2 for archival
        if self.storage:
            try:
                await self.storage.upload_bytes(f"images/{file_id}.png", image_bytes)
            except Exception as e:
                logger.error(f"Failed to upload image to storage: {e}")
        else:
            logger.info("Storage interface not provided. Skipping image archival upload.")

        # 2. Dynamic robust prompt based on character description (any lively gesturing/movement is great!)
        char_desc = character_description or "a simple black stick figure"
        action = "moving, gesturing, and animating naturally with lively motion, bringing the drawing to life"
        custom_prompt = f"{char_desc} {action} on a solid green background, no text, no watermarks, no captions, no letters"

        # 3. Submit to Veo
        operation_name = await self._submit_to_veo(custom_prompt, image_bytes, project_id, aspect_ratio, file_id, env)

        return operation_name, original_direction

    async def _submit_to_veo(self, custom_prompt: str, image_bytes: bytes, project_id: str, aspect_ratio: str, file_id: str, env: Any) -> str:
        """Submit to Veo with a direction-neutral prompt."""
        
        final_prompt = (
            f"{custom_prompt}. "
            "Animate the character moving forward and animating naturally in the direction it is naturally facing in the starting image. "
            "Strictly maintain the exact 2D black and white line art drawing style of the first frame throughout the entire video. "
            "Static camera, locked background, side-view perspective. "
            "Do not turn the character around, do not rotate 180 degrees, do not change facing direction at any point. "
            "Keep the character shape, topology, and lines perfectly consistent. "
            "No text, no watermarks, no captions. "
            "Animation starts seamlessly from the provided image as the exact first frame. Smooth motion."
        )
        logger.info(f"Final Veo prompt: {final_prompt}")

        try:
            url = f"https://{self.settings.google_cloud_location}-aiplatform.googleapis.com/v1/projects/{project_id}/locations/{self.settings.google_cloud_location}/publishers/google/models/{self.settings.veo_model_name}:predictLongRunning"
            token = await get_access_token(self.settings, self.http_client, self.token_store)

            image_b64 = base64.b64encode(image_bytes).decode('utf-8')

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}"
            }
            payload = {
                "instances": [
                    {
                        "prompt": final_prompt,
                        "image": {
                            "bytesBase64Encoded": image_b64,
                            "mimeType": "image/png"
                        }
                    }
                ],
                "parameters": {
                    "aspectRatio": aspect_ratio,
                    "durationSeconds": 4,
                    "includeAudio": False,
                    "resolution": "720p",
                    "fps": 24,
                    "negativePrompt": (
                        "turning around, spinning, looking backwards, changing facing direction, "
                        "rotating 180 degrees, turning back, flipping direction, "
                        "camera movement, zoom, pan, tilt, rotation, moving camera, dynamic camera angles, "
                        "text, watermark, caption, letters, numbers, subtitle, signature, logo, "
                        "3d render, shading, shadows, gradients, volumetric lighting, "
                        "audio, sound, speech, photorealistic, style change, character redesign"
                    )
                }
            }

            res_json = await self.http_client.post_json(url, headers, payload)
            operation_name = res_json.get("name")
            logger.info(f"Veo operation started: {operation_name}")
            return operation_name

        except Exception as e:
            logger.error(f"Failed to submit to Veo: {e}")
            raise e

    # ── check_status ──────────────────────────────────────────────────────────

    async def check_status(self, provider_task_id: str, env: Any = None) -> ProviderResult:
        if provider_task_id.startswith("mock-"):
            return ProviderResult(status=ProviderStatus.FAILED, error="Ignoring old mock task in Gemini provider")

        project_id = self.settings.gcp_project_id

        try:
            parts = provider_task_id.rpartition('/operations/')
            if parts[1]:
                resource_name = parts[0]
            else:
                resource_name = provider_task_id

            url = f"https://{self.settings.google_cloud_location}-aiplatform.googleapis.com/v1beta1/{resource_name}:fetchPredictOperation"
            token = await get_access_token(self.settings, self.http_client, self.token_store)

            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            payload = {
                "operationName": provider_task_id
            }

            res_json = await self.http_client.post_json(url, headers, payload)

            done = res_json.get("done", False)
            logger.info(f"Veo status: done={done}, id={provider_task_id.split('/')[-1]}")

            if not done:
                return ProviderResult(status=ProviderStatus.PROCESSING)

            if "error" in res_json:
                logger.error(f"Veo operation error: {res_json['error']}")
                return ProviderResult(status=ProviderStatus.FAILED, error=str(res_json["error"]))

            resp_obj = res_json.get("response", {})
            video_bytes = None
            try:
                videos = resp_obj.get("generatedVideos", [])
                if not videos:
                    videos = resp_obj.get("videos", [])

                if videos:
                    video_b64 = videos[0].get("bytesBase64Encoded")
                    if not video_b64 and "video" in videos[0]:
                        video_b64 = videos[0]["video"].get("bytesBase64Encoded")

                    if video_b64:
                        video_bytes = base64.b64decode(video_b64)
            except Exception as e:
                logger.warning(f"Could not parse video bytes from response: {e}")

            if not video_bytes:
                logger.error(f"No video bytes found in response. Available keys: {list(resp_obj.keys())}")
                return ProviderResult(status=ProviderStatus.FAILED, error="No video bytes found in response")

            # We no longer verify direction post-generation. The frontend flips left-facing images
            # to right before upload, so Veo always generates a right-facing video. The original
            # direction is stored in the DB during submission.
            facing_direction = None

            filename = f"{provider_task_id.split('/')[-1]}.mp4"
            r2_key = f"videos/{filename}"

            if self.storage:
                try:
                    await self.storage.upload_bytes(r2_key, video_bytes)
                except Exception as e:
                    logger.error(f"Failed to upload video to storage: {e}")
                    return ProviderResult(status=ProviderStatus.FAILED, error="Failed to upload video to R2")
            else:
                logger.info("Storage interface not available. Saving to local file for testing.")
                os.makedirs("videos", exist_ok=True)
                with open(f"videos/{filename}", "wb") as f:
                    f.write(video_bytes)

            r2_public_url = self.settings.r2_public_url.rstrip("/")
            video_url = f"{r2_public_url}/{r2_key}"
            logger.info(f"Video ready at: {video_url}")

            return ProviderResult(status=ProviderStatus.COMPLETED, video_url=video_url, facing_direction=facing_direction)

        except Exception as e:
            msg = str(e)
            terminal_status = _terminal_http_status(msg)
            if terminal_status is not None:
                # Operation is gone/invalid — mark FAILED so the artwork stops
                # being polled forever instead of staying "generating".
                logger.error(f"check_status: non-recoverable HTTP {terminal_status}, marking FAILED: {e}")
                return ProviderResult(status=ProviderStatus.FAILED, error=msg)
            # Transient (5xx / 429 / 408 / network / parse): retry next poll.
            logger.warning(f"check_status: transient error, will retry next poll: {e}")
            return ProviderResult(status=ProviderStatus.PROCESSING)
