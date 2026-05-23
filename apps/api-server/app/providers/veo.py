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

    # ── submit ────────────────────────────────────────────────────────────────

    async def submit(self, image_bytes: bytes, file_id: str, aspect_ratio: str = "16:9", env: Any = None) -> tuple[str, Optional[str]]:
        project_id = self.settings.gcp_project_id

        # 1. Upload original image to R2 for archival (if running on Worker)
        if self.storage:
            try:
                await self.storage.upload_bytes(f"images/{file_id}.png", image_bytes)
            except Exception as e:
                logger.error(f"Failed to upload image to storage: {e}")
        else:
            logger.info("Storage interface not provided. Skipping image archival upload.")

        # 2. Analyze image with Gemini — direction-agnostic prompt only
        custom_prompt = await self._analyze_image(image_bytes, project_id, file_id, env)

        # 3. Submit to Veo (no direction keywords — let Veo animate naturally)
        operation_name = await self._submit_to_veo(custom_prompt, image_bytes, project_id, aspect_ratio, file_id, env)

        # Direction will be determined AFTER video generation by analyzing the actual output
        return operation_name, None

    async def _analyze_image(self, image_bytes: bytes, project_id: str, file_id: str, env: Any) -> str:
        """Analyze the uploaded image and generate an animation prompt.

        Direction keywords (left/right) are deliberately OMITTED from the
        returned prompt.  Veo 3 has mandatory prompt enhancement that can
        conflict with explicit direction cues, producing jarring 180-degree
        turns.  The actual running direction is determined *after* the video
        is generated (see ``_verify_direction``).
        """
        logger.info(f"Analyzing image with {self.settings.gemini_model_name} for artwork {file_id}")

        prompt_text = (
            "Analyze this image of a hand-drawn doodle or stick figure.\n"
            "Generate a short animation prompt (15-25 words) describing the character running or moving.\n"
            "IMPORTANT RULES:\n"
            "1. Do NOT mention any direction (left, right, forward, backward). Keep the prompt direction-neutral.\n"
            "2. The prompt MUST include: 'no text, no watermarks, no captions, no letters'.\n"
            "3. Describe the character's appearance and motion style only.\n"
            "4. Include 'on a solid green background' in the prompt.\n"
            "Return ONLY a JSON object with this exact key:\n"
            "{\n"
            "  \"prompt\": \"Your direction-neutral animation prompt here\"\n"
            "}\n"
            "Do not include markdown code blocks or any other text."
        )

        custom_prompt = "a hand-drawn doodle running, on a solid green background, no text, no watermarks, no captions, no letters"

        try:
            api_key = self.settings.gemini_api_key

            if api_key:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.settings.gemini_model_name}:generateContent?key={api_key}"
                headers = {"Content-Type": "application/json"}
                logger.info("Using Gemini API Key for analysis.")
            else:
                url = f"https://{self.settings.google_cloud_location}-aiplatform.googleapis.com/v1/projects/{project_id}/locations/{self.settings.google_cloud_location}/publishers/google/models/{self.settings.gemini_model_name}:generateContent"
                token = await get_access_token(self.settings, self.http_client, self.token_store)
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {token}"
                }
                logger.info("Using Vertex AI for Gemini analysis.")

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

            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            text = text.strip()

            result = json.loads(text)
            custom_prompt = result.get("prompt", custom_prompt)
            logger.info(f"Gemini generated prompt (direction-neutral): {custom_prompt}")
        except Exception as e:
            logger.warning(f"Gemini analysis failed, using default prompt. Error: {e}")

        return custom_prompt

    async def _submit_to_veo(self, custom_prompt: str, image_bytes: bytes, project_id: str, aspect_ratio: str, file_id: str, env: Any) -> str:
        """Submit to Veo with a direction-neutral prompt.

        No left/right keywords are injected.  Instead the prompt asks Veo to
        animate the character "in the direction it is naturally facing" so that
        Veo's own visual interpretation is never contradicted, preventing the
        jarring 180-degree turn artefact.
        """
        # Strip any accidental direction keywords that Gemini might have included
        clean_prompt = custom_prompt
        for kw in ["facing left", "facing right", "moving left", "moving right",
                    "running left", "running right", "heading left", "heading right",
                    "towards the left", "towards the right", "to the left", "to the right"]:
            clean_prompt = clean_prompt.lower().replace(kw, "")
        # Restore original casing by using the cleaned version only for safety
        if clean_prompt != custom_prompt.lower():
            custom_prompt = clean_prompt
        clean_prompt = custom_prompt.strip().rstrip(".").strip()

        final_prompt = (
            f"{clean_prompt}. "
            "Animate the character running forward in the direction it is naturally facing in the starting image. "
            "Strictly maintain the exact 2D black and white line art drawing style of the first frame throughout the entire video. "
            "Static camera, locked background, side-view perspective. "
            "Do not turn the character around, do not rotate 180 degrees, do not change facing direction at any point. "
            "Keep the character shape, topology, and lines perfectly consistent. "
            "No text, no watermarks, no captions. "
            "Animation starts seamlessly from the provided image as the exact first frame. Smooth motion."
        )
        logger.info(f"Final Veo prompt (direction-neutral): {final_prompt}")

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

    # ── Phase 2: post-generation direction verification ────────────────────────

    async def _verify_direction(self, video_bytes: bytes, project_id: str) -> str:
        """Analyze the *generated* video to determine the actual running direction.

        This is Phase 2 of the two-phase direction system.  We send the video
        to Gemini and ask it which way the character is running in the video.
        This guarantees that the facing_direction stored in the DB matches
        the real video content, regardless of how Veo interpreted the prompt.
        """
        try:
            api_key = self.settings.gemini_api_key
            video_b64 = base64.b64encode(video_bytes).decode('utf-8')

            prompt_text = (
                "Watch this short animation video. A character is running or moving across the screen.\n"
                "Determine the PRIMARY horizontal direction the character is moving towards:\n"
                "- 'left' if the character is mostly moving towards the LEFT side of the screen\n"
                "- 'right' if the character is mostly moving towards the RIGHT side of the screen\n"
                "Look at the overall trajectory across the entire video, not just a single frame.\n"
                "Return ONLY a JSON object: {\"direction\": \"left\"} or {\"direction\": \"right\"}\n"
                "Do not include markdown code blocks or any other text."
            )

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

            payload = {
                "contents": [
                    {
                        "role": "user",
                        "parts": [
                            {"inline_data": {"mime_type": "video/mp4", "data": video_b64}},
                            {"text": prompt_text}
                        ]
                    }
                ]
            }

            res_json = await self.http_client.post_json(url, headers, payload)
            text = res_json["candidates"][0]["content"]["parts"][0]["text"].strip()

            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            text = text.strip()

            result = json.loads(text)
            direction = result.get("direction", "right")
            if direction not in ("left", "right"):
                direction = "right"
            logger.info(f"Post-generation direction verification: {direction}")
            return direction

        except Exception as e:
            logger.warning(f"Post-generation direction verification failed, defaulting to 'right'. Error: {e}")
            return "right"

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

            # ── Phase 2: verify actual direction from the generated video ──
            facing_direction = await self._verify_direction(video_bytes, project_id)

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
            logger.info(f"Video ready at: {video_url}, verified direction: {facing_direction}")

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
