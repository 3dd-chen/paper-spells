"""
Google Gemini API (REST) + Cloudflare R2 production provider.

Flow:
  submit()      → Gemini analyzes drawing via REST → Veo generates video via REST → returns operation name
  check_status() → polls operation via REST → downloads from GCS via HTTP → uploads to R2 via binding → returns public URL
"""
from __future__ import annotations
import asyncio
import base64
import logging
from typing import Optional, Any

import httpx

from app.providers.base import AIProvider, ProviderResult, ProviderStatus

logger = logging.getLogger(__name__)


class GeminiVeoProvider(AIProvider):
    def __init__(self) -> None:
        pass

    # ── submit ────────────────────────────────────────────────────────────────

    async def submit(self, image_bytes: bytes, file_id: str, aspect_ratio: str = "16:9", env: Any = None) -> tuple[str, Optional[str]]:
        if not env:
            logger.error("Environment object (env) is required!")
            raise ValueError("Environment object is required")

        api_key = env.GEMINI_API_KEY or env.GOOGLE_API_KEY
        gcs_output_uri = env.GCS_OUTPUT_BUCKET_URI

        base64_image = base64.b64encode(image_bytes).decode("utf-8")

        # 1. Upload original image to R2 for archival using binding
        try:
            await env.BUCKET.put(f"images/{file_id}.png", image_bytes)
            logger.info(f"Uploaded image to R2 via binding: images/{file_id}.png")
        except Exception as e:
            logger.error(f"Failed to upload image to R2 via binding: {e}")

        if not api_key:
            logger.error("GEMINI_API_KEY or GOOGLE_API_KEY is not set in env!")
            raise ValueError("API Key is required")

        # 2. Analyze image with Gemini → generate a custom Veo prompt
        logger.info(f"Analyzing image with Gemini for artwork {file_id}")
        
        prompt_text = (
            "Determine if the character or object is naturally facing 'left' or 'right'. If unclear, default to 'right'.\n"
            "IMPORTANT: You MUST include the detected direction in the generated 'prompt' (e.g., 'facing left', 'moving to the left') so that Veo generates the video in the correct orientation matching the original drawing!\n"
            "Return ONLY a JSON object with the following keys:\n"
            "{\n"
            "  \"prompt\": \"The final prompt for the video generator (15-25 words), explicitly stating the direction\",\n"
            "  \"direction\": \"left\" or \"right\"\n"
            "}\n"
            "Do not include markdown code blocks or any other text."
        )

        custom_prompt = "a hand-drawn doodle coming to life, simple clean background, no text, smooth animation"
        facing_direction = "right"

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}",
                    json={
                        "contents": [{
                            "parts": [
                                {"inline_data": {"mime_type": "image/png", "data": base64_image}},
                                {"text": prompt_text}
                            ]
                        }]
                    },
                    timeout=30.0
                )
                
                if resp.status_code == 200:
                    result_json = resp.json()
                    text = result_json["candidates"][0]["content"]["parts"][0]["text"].strip()
                    
                    # Strip markdown code blocks if present
                    if text.startswith("```"):
                        text = text.split("```")[1]
                        if text.startswith("json"):
                            text = text[4:]
                    text = text.strip()
                    
                    import json
                    result = json.loads(text)
                    custom_prompt = result.get("prompt", custom_prompt)
                    facing_direction = result.get("direction", facing_direction)
                    logger.info(f"Gemini generated prompt: {custom_prompt}, direction: {facing_direction}")
                else:
                    logger.warning(f"Gemini API failed with status {resp.status_code}: {resp.text}")
        except Exception as e:
            logger.warning(f"Gemini analysis failed, using default prompt. Error: {e}")

        # 3. Submit to Veo
        logger.info(
            f"Submitting to Veo: file_id={file_id}, aspect_ratio={aspect_ratio}"
        )
        
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/veo-3.1-lite-generate-001:generateVideos?key={api_key}",
                    json={
                        "prompt": custom_prompt,
                        "image": {"inline_data": {"mime_type": "image/png", "data": base64_image}},
                        "config": {
                            "aspect_ratio": aspect_ratio,
                            "number_of_videos": 1,
                            "duration_seconds": 4,
                            "output_gcs_uri": f"{gcs_output_uri.rstrip('/')}/{file_id}/"
                        }
                    },
                    timeout=30.0
                )
                
                if resp.status_code == 200:
                    op_json = resp.json()
                    operation_name = op_json["name"]
                    logger.info(f"Veo operation started: {operation_name}")
                    return operation_name, facing_direction
                else:
                    logger.error(f"Veo API failed with status {resp.status_code}: {resp.text}")
                    raise ValueError(f"Veo API failed: {resp.text}")
        except Exception as e:
            logger.error(f"Failed to submit to Veo: {e}")
            raise e

    # ── check_status ──────────────────────────────────────────────────────────

    async def check_status(self, provider_task_id: str, env: Any = None) -> ProviderResult:
        if not env:
            return ProviderResult(status=ProviderStatus.FAILED, error="Environment object is required")

        api_key = env.GEMINI_API_KEY or env.GOOGLE_API_KEY
        r2_public_url = env.R2_PUBLIC_URL

        if not api_key:
            return ProviderResult(status=ProviderStatus.FAILED, error="API Key is required")

        try:
            async with httpx.AsyncClient() as client:
                # Poll the operation
                resp = await client.get(
                    f"https://generativelanguage.googleapis.com/v1beta/{provider_task_id}?key={api_key}",
                    timeout=30.0
                )
                
                if resp.status_code != 200:
                    logger.error(f"Failed to poll operation {provider_task_id}: {resp.text}")
                    return ProviderResult(status=ProviderStatus.PROCESSING)
                
                op_json = resp.json()
                done = op_json.get("done", False)
                logger.info(f"Veo status: done={done}, id={provider_task_id[-36:]}")

                if not done:
                    return ProviderResult(status=ProviderStatus.PROCESSING)

                if "error" in op_json:
                    logger.error(f"Veo operation error: {op_json['error']}")
                    return ProviderResult(status=ProviderStatus.FAILED, error=str(op_json["error"]))

                response_data = op_json.get("response", {})
                generated_videos = response_data.get("generatedVideos", [])
                
                if not generated_videos:
                    logger.error(f"Veo response empty or no videos. Response: {response_data}")
                    return ProviderResult(status=ProviderStatus.FAILED, error="No video generated")

                # Download from GCS via HTTP (since bucket is public)
                video_uri: str = generated_videos[0]["video"]["uri"]
                bucket_name = video_uri.split("/")[2]
                blob_name = "/".join(video_uri.split("/")[3:])
                
                public_url = f"https://storage.googleapis.com/{bucket_name}/{blob_name}"
                logger.info(f"Downloading video from public GCS URL: {public_url}")
                
                resp = await client.get(public_url, timeout=30.0)
                if resp.status_code != 200:
                    logger.error(f"Failed to download from GCS: {resp.status_code} {resp.text}")
                    return ProviderResult(status=ProviderStatus.FAILED, error="Failed to download video from GCS")
                
                video_bytes = resp.content
                logger.info(f"Downloaded {len(video_bytes)} bytes from GCS")

                # Build a unique R2 key using the GCS subfolder name to avoid overwrites
                parts = video_uri.split("/")
                gcs_folder = parts[-2] if len(parts) >= 2 else "unknown"
                filename = parts[-1]
                r2_key = f"videos/{gcs_folder}_{filename}"

                # Upload to R2 via binding
                try:
                    await env.BUCKET.put(r2_key, video_bytes)
                    logger.info(f"Uploaded video to R2 via binding: {r2_key}")
                except Exception as e:
                    logger.error(f"Failed to upload video to R2 via binding: {e}")
                    return ProviderResult(status=ProviderStatus.FAILED, error="Failed to upload video to R2")

                video_url = f"{r2_public_url.rstrip('/')}/{r2_key}"
                logger.info(f"Video ready at: {video_url}")
                return ProviderResult(status=ProviderStatus.COMPLETED, video_url=video_url)

        except Exception as e:
            import traceback
            logger.error(f"Error in check_status: {type(e).__name__}: {e}\n{traceback.format_exc()}")
            return ProviderResult(status=ProviderStatus.PROCESSING)
