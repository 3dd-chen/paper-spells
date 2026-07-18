from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)

class StorageInterface(ABC):
    @abstractmethod
    async def upload_bytes(self, path: str, data: bytes) -> None:
        pass

    @abstractmethod
    async def delete(self, path: str) -> None:
        pass

class CloudflareR2Storage(StorageInterface):
    def __init__(self, bucket):
        self.bucket = bucket

    async def upload_bytes(self, path: str, data: bytes) -> None:
        import js
        from pyodide.ffi import to_js
        try:
            # Detect content type based on path extension
            content_type = "application/octet-stream"
            if path.lower().endswith(".png"):
                content_type = "image/png"
            elif path.lower().endswith(".mp4"):
                content_type = "video/mp4"
            elif path.lower().endswith((".jpeg", ".jpg")):
                content_type = "image/jpeg"

            # Set R2 options including public caching headers (1 year cache)
            py_options = {
                "httpMetadata": {
                    "contentType": content_type,
                    "cacheControl": "public, max-age=31536000"
                }
            }
            js_options = to_js(py_options, dict_converter=js.Object.fromEntries)

            js_bytes = js.Uint8Array.new(data)
            await self.bucket.put(path, js_bytes, js_options)
            logger.info(f"Uploaded {path} to R2 (type={content_type})")
        except Exception as e:
            logger.error(f"R2 Upload failed for {path}: {e}")
            raise

    async def delete(self, path: str) -> None:
        try:
            await self.bucket.delete(path)
            logger.info(f"Deleted {path} from R2")
        except Exception as e:
            logger.warning(f"R2 Delete failed for {path}: {e}")
