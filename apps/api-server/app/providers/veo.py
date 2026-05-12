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

from js import fetch

from app.providers.base import AIProvider, ProviderResult, ProviderStatus
from app.providers.gcp_auth import get_access_token

logger = logging.getLogger(__name__)


class GeminiVeoProvider(AIProvider):
    def __init__(self) -> None:
        pass

    # ── submit ────────────────────────────────────────────────────────────────

    async def submit(self, image_bytes: bytes, file_id: str, aspect_ratio: str = "16:9", env: Any = None) -> tuple[str, Optional[str]]:
        # Read Project ID from env object or os.environ
        project_id = "project-68d02a87-0962-4fe5-a9a"  # Fallback

        if env and hasattr(env, "GCP_PROJECT_ID"):
            project_id = env.GCP_PROJECT_ID
        elif os.getenv("GCP_PROJECT_ID"):
            project_id = os.getenv("GCP_PROJECT_ID")

        # 1. Upload original image to R2 for archival (if running on Worker)
        if env and hasattr(env, "BUCKET"):
            try:
                # Cloudflare R2 binding
                await env.BUCKET.put(f"images/{file_id}.png", image_bytes)
                logger.info(f"Uploaded image to R2: images/{file_id}.png")
            except Exception as e:
                logger.error(f"Failed to upload image to R2: {e}")
        else:
            logger.info("R2 binding not available. Skipping image archival upload.")

        # 2. Analyze image with Gemini 2.5 Flash Lite on Vertex AI
        logger.info(f"Analyzing image with Gemini 2.5 Flash Lite on Vertex AI for artwork {file_id}")
        
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
            # Vertex AI endpoint for Gemini 2.5 Flash Lite
            url = f"https://us-central1-aiplatform.googleapis.com/v1/projects/{project_id}/locations/us-central1/publishers/google/models/gemini-2.5-flash-lite:generateContent"
            token = await get_access_token(env)
            
            image_b64 = base64.b64encode(image_bytes).decode('utf-8')
            
            response = await fetch(
                url,
                method="POST",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {token}"
                },
                body=json.dumps({
                    "contents": [
                        {
                            "role": "user",
                            "parts": [
                                {"inline_data": {"mime_type": "image/png", "data": image_b64}},
                                {"text": prompt_text}
                            ]
                        }
                    ]
                })
            )
            
            if response.status == 200:
                res_json = (await response.json()).to_py()
                text = res_json["candidates"][0]["content"]["parts"][0]["text"].strip()
                
                # Strip markdown code blocks if present
                if text.startswith("```"):
                    text = text.split("```")[1]
                    if text.startswith("json"):
                        text = text[4:]
                text = text.strip()
                
                result = json.loads(text)
                custom_prompt = result.get("prompt", custom_prompt)
                facing_direction = result.get("direction", facing_direction)
                logger.info(f"Gemini generated prompt: {custom_prompt}, direction: {facing_direction}")
            else:
                resp_text = await response.text()
                logger.warning(f"Gemini analysis failed with status {response.status}: {resp_text}, using default prompt.")
        except Exception as e:
            logger.warning(f"Gemini analysis failed, using default prompt. Error: {e}")

        # Add negative prompt for audio to save money!
        custom_prompt += ", silent video, no sound, no audio track, no background music"

        # 3. Submit to Veo 3.1 Lite (via predictLongRunning on Vertex AI)
        logger.info(
            f"Submitting to Veo 3.1 Lite on Vertex AI: file_id={file_id}, aspect_ratio={aspect_ratio}"
        )
        
        try:
            # Vertex AI endpoint for Veo 3.1 Lite
            url = f"https://us-central1-aiplatform.googleapis.com/v1/projects/{project_id}/locations/us-central1/publishers/google/models/veo-3.1-lite-generate-001:predictLongRunning"
            token = await get_access_token(env)
            
            image_b64 = base64.b64encode(image_bytes).decode('utf-8')
            
            response = await fetch(
                url,
                method="POST",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {token}"
                },
                body=json.dumps({
                    "instances": [
                        {
                            "prompt": custom_prompt,
                            "image": {
                                "bytesBase64Encoded": image_b64,
                                "mimeType": "image/png"
                            }
                        }
                    ],
                    "parameters": {
                        "aspectRatio": aspect_ratio,
                        "durationSeconds": 4
                        # Note: We DO NOT provide outputStorageUri to get bytes back!
                    }
                })
            )
            
            if response.status == 200:
                res_json = (await response.json()).to_py()
                operation_name = res_json.get("name")
                logger.info(f"Veo operation started: {operation_name}")
                return operation_name, facing_direction
            else:
                resp_text = await response.text()
                logger.error(f"Veo submission failed with status {response.status}: {resp_text}")
                raise Exception(f"Veo submission failed with status {response.status}")
                    
        except Exception as e:
            logger.error(f"Failed to submit to Veo: {e}")
            raise e

    # ── check_status ──────────────────────────────────────────────────────────

    async def check_status(self, provider_task_id: str, env: Any = None) -> ProviderResult:
        if provider_task_id.startswith("mock-"):
            return ProviderResult(status=ProviderStatus.FAILED, error="Ignoring old mock task in Gemini provider")

        # Read Project ID
        project_id = "project-68d02a87-0962-4fe5-a9a"  # Fallback
        if env and hasattr(env, "GCP_PROJECT_ID"):
            project_id = env.GCP_PROJECT_ID
        elif os.getenv("GCP_PROJECT_ID"):
            project_id = os.getenv("GCP_PROJECT_ID")

        try:
            # Poll the operation using the correct URL (Vertex AI operations URL)
            # The provider_task_id returned by Vertex AI is the full resource name:
            # projects/.../locations/us-central1/publishers/google/models/.../operations/...
            url = f"https://us-central1-aiplatform.googleapis.com/v1/{provider_task_id}"
            token = await get_access_token(env)
            
            response = await fetch(
                url,
                method="GET",
                headers={"Authorization": f"Bearer {token}"}
            )
            
            if response.status != 200:
                resp_text = await response.text()
                logger.error(f"Failed to poll Veo operation: {response.status} - {resp_text}")
                return ProviderResult(status=ProviderStatus.PROCESSING)
            
            res_json = (await response.json()).to_py()
                
            # Check if done
            done = res_json.get("done", False)
            logger.info(f"Veo status: done={done}, id={provider_task_id.split('/')[-1]}")

            if not done:
                return ProviderResult(status=ProviderStatus.PROCESSING)

            # Check for error
            if "error" in res_json:
                logger.error(f"Veo operation error: {res_json['error']}")
                return ProviderResult(status=ProviderStatus.FAILED, error=str(res_json["error"]))

            # Operation is done and successful!
            # Since we didn't use storage URI, the bytes should be in the response!
            resp_obj = res_json.get("response", {})
            
            # The format for Vertex AI predictLongRunning usually has `generatedVideos`
            video_bytes = None
            try:
                videos = resp_obj.get("generatedVideos", [])
                if videos:
                    video_b64 = videos[0]["video"].get("bytesBase64Encoded")
                    if video_b64:
                        video_bytes = base64.b64decode(video_b64)
            except Exception as e:
                logger.warning(f"Could not parse video bytes from response: {e}")

            if not video_bytes:
                logger.error(f"No video bytes found in response: {resp_obj}")
                return ProviderResult(status=ProviderStatus.FAILED, error="No video bytes found in response")

            # Upload to R2
            filename = f"{provider_task_id.split('/')[-1]}.mp4"
            r2_key = f"videos/{filename}"

            if env and hasattr(env, "BUCKET"):
                try:
                    # Cloudflare R2 binding
                    await env.BUCKET.put(r2_key, video_bytes)
                    logger.info(f"Uploaded video to R2: {r2_key}")
                except Exception as e:
                    logger.error(f"Failed to upload video to R2: {e}")
                    return ProviderResult(status=ProviderStatus.FAILED, error="Failed to upload video to R2")
            else:
                logger.info("R2 binding not available. Saving to local file for testing.")
                os.makedirs("videos", exist_ok=True)
                with open(f"videos/{filename}", "wb") as f:
                    f.write(video_bytes)

            r2_public_url = os.getenv("R2_PUBLIC_URL", "https://media.hissnake.com").rstrip("/")
            video_url = f"{r2_public_url}/{r2_key}"
            logger.info(f"Video ready at: {video_url}")
            
            return ProviderResult(status=ProviderStatus.COMPLETED, video_url=video_url)

        except Exception as e:
            logger.error(f"Error in check_status: {e}")
            return ProviderResult(status=ProviderStatus.PROCESSING)
