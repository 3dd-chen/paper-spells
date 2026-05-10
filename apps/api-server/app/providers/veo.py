"""
Google Vertex AI (Veo) + Cloudflare R2 production provider.

Flow:
  submit()      → Gemini analyzes drawing → Veo generates video → returns GCP operation name
  check_status() → polls GCP operation → downloads from GCS → uploads to R2 → returns public URL
"""
from __future__ import annotations
import asyncio
import logging
import os
from typing import Optional

import boto3
from google import genai
from google.genai import types
from google.cloud import storage as gcs

from app.config import (
    R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY,
    R2_BUCKET_NAME, R2_PUBLIC_URL, GCS_OUTPUT_BUCKET_URI,
)
from app.providers.base import AIProvider, ProviderResult, ProviderStatus

logger = logging.getLogger(__name__)


class GeminiVeoProvider(AIProvider):
    def __init__(self) -> None:
        self.r2 = boto3.client(
            service_name="s3",
            endpoint_url=f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
            aws_access_key_id=R2_ACCESS_KEY_ID,
            aws_secret_access_key=R2_SECRET_ACCESS_KEY,
            region_name="auto",
        )
        self.r2_bucket = R2_BUCKET_NAME
        self.r2_public_url = R2_PUBLIC_URL

        self.genai_client = genai.Client()
        self.gcs_client = gcs.Client()
        self.gcs_output_uri = GCS_OUTPUT_BUCKET_URI

    # ── submit ────────────────────────────────────────────────────────────────

    async def submit(self, image_path: str, aspect_ratio: str = "16:9") -> tuple[str, Optional[str]]:
        file_id = os.path.basename(image_path).split(".")[0]
        loop = asyncio.get_running_loop()

        # 1. Upload original image to R2 for archival
        def _upload_image_to_r2() -> None:
            with open(image_path, "rb") as f:
                self.r2.put_object(
                    Bucket=self.r2_bucket,
                    Key=f"images/{file_id}.png",
                    Body=f.read(),
                    ContentType="image/png",
                )

        await loop.run_in_executor(None, _upload_image_to_r2)

        # 2. Analyze image with Gemini → generate a custom Veo prompt
        def _submit_veo() -> tuple[str, str]:
            with open(image_path, "rb") as f:
                image_bytes = f.read()

            logger.info(f"Analyzing image with Gemini for artwork {file_id}")
            try:
                analysis = self.genai_client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=[
                        types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
                        (
                            "Also, determine if the character or object is naturally facing 'left' or 'right'. If unclear, default to 'right'.\n"
                            "IMPORTANT: You MUST include the detected direction in the generated 'prompt' (e.g., 'facing left', 'moving to the left') so that Veo generates the video in the correct orientation matching the original drawing!\n"
                            "Return ONLY a JSON object with the following keys:\n"
                            "{\n"
                            "  \"prompt\": \"The final prompt for the video generator (15-25 words), explicitly stating the direction\",\n"
                            "  \"direction\": \"left\" or \"right\"\n"
                            "}\n"
                            "Do not include markdown code blocks or any other text."
                        ),
                    ],
                )
                import json
                text = analysis.text.strip()
                # Strip markdown code blocks if present
                if text.startswith("```"):
                    text = text.split("```")[1]
                    if text.startswith("json"):
                        text = text[4:]
                text = text.strip()
                
                result = json.loads(text)
                custom_prompt = result.get("prompt", "")
                facing_direction = result.get("direction", "right")
                logger.info(f"Gemini generated prompt: {custom_prompt}, direction: {facing_direction}")
            except Exception as e:
                logger.warning(f"Gemini analysis failed, using default prompt. Error: {e}")
                custom_prompt = "a hand-drawn doodle coming to life, simple clean background, no text, smooth animation"
                facing_direction = "right"

            # 3. Submit to Veo
            logger.info(
                f"Submitting to Veo: image_size={len(image_bytes)} bytes, "
                f"file_id={file_id}, aspect_ratio={aspect_ratio}"
            )
            operation = self.genai_client.models.generate_videos(
                model="veo-3.1-lite-generate-001",
                prompt=custom_prompt,
                image=types.Image(image_bytes=image_bytes, mime_type="image/png"),
                config=types.GenerateVideosConfig(
                    aspect_ratio=aspect_ratio,
                    number_of_videos=1,
                    duration_seconds=4,
                    output_gcs_uri=f"{self.gcs_output_uri.rstrip('/')}/{file_id}/",
                ),
            )
            logger.info(f"Veo operation started: {operation.name}")
            return operation.name, facing_direction

        return await loop.run_in_executor(None, _submit_veo)

    # ── check_status ──────────────────────────────────────────────────────────

    async def check_status(self, provider_task_id: str) -> ProviderResult:
        loop = asyncio.get_running_loop()

        def _do_check() -> ProviderResult:
            try:
                from google.genai.types import GenerateVideosOperation
                # The SDK expects a GenerateVideosOperation instance
                op_ref = GenerateVideosOperation()
                op_ref.name = provider_task_id
                
                operation = self.genai_client.operations.get(op_ref)
                logger.info(f"Veo status: done={operation.done}, id={provider_task_id[-36:]}")

                if not operation.done:
                    return ProviderResult(status=ProviderStatus.PROCESSING)

                if getattr(operation, "error", None):
                    logger.error(f"Veo operation error: {operation.error}")
                    return ProviderResult(status=ProviderStatus.FAILED, error=str(operation.error))

                if not operation.response or not operation.response.generated_videos:
                    logger.error(f"Veo response empty or no videos. Response: {operation.response}")
                    return ProviderResult(status=ProviderStatus.FAILED, error="No video generated")

                # Download from GCS
                video_uri: str = operation.response.generated_videos[0].video.uri
                bucket_name = video_uri.split("/")[2]
                blob_name = "/".join(video_uri.split("/")[3:])
                video_bytes = self.gcs_client.bucket(bucket_name).blob(blob_name).download_as_bytes()
                logger.info(f"Downloaded {len(video_bytes)} bytes from GCS: {video_uri}")

                # Build a unique R2 key using the GCS subfolder name to avoid overwrites
                parts = video_uri.split("/")
                gcs_folder = parts[-2] if len(parts) >= 2 else "unknown"
                filename = parts[-1]
                r2_key = f"videos/{gcs_folder}_{filename}"

                self.r2.put_object(
                    Bucket=self.r2_bucket,
                    Key=r2_key,
                    Body=video_bytes,
                    ContentType="video/mp4",
                )
                logger.info(f"Uploaded video to R2: {r2_key}")

                video_url = f"{self.r2_public_url}/{r2_key}"
                logger.info(f"Video ready at: {video_url}")
                return ProviderResult(status=ProviderStatus.COMPLETED, video_url=video_url)

            except Exception as e:
                import traceback
                logger.error(f"Error in check_status: {type(e).__name__}: {e}\n{traceback.format_exc()}")
                # Return PROCESSING so the gallery retries on the next poll
                return ProviderResult(status=ProviderStatus.PROCESSING)

        return await loop.run_in_executor(None, _do_check)
