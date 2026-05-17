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
        try:
            js_bytes = js.Uint8Array.new(data)
            await self.bucket.put(path, js_bytes)
            logger.info(f"Uploaded {path} to R2")
        except Exception as e:
            logger.error(f"R2 Upload failed: {e}")
            raise

    async def delete(self, path: str) -> None:
        try:
            await self.bucket.delete(path)
            logger.info(f"Deleted {path} from R2")
        except Exception as e:
            logger.warning(f"R2 Delete failed for {path}: {e}")
