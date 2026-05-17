from __future__ import annotations
from typing import List, Optional
import uuid
import hashlib
import hmac
import os
from enum import Enum

class ArtworkStatus(str, Enum):
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"

class ArtworkRepository:
    def __init__(self, db):
        self.db = db

    async def create_artwork(self, image_path: str, room_id: str) -> dict:
        task_id = str(uuid.uuid4())
        await self.db.prepare(
            "INSERT INTO artworks (id, room_id, image_path, status) VALUES (?, ?, ?, ?)"
        ).bind(task_id, room_id, image_path, ArtworkStatus.PENDING.value).run()
        
        return {
            "id": task_id,
            "room_id": room_id,
            "image_path": image_path,
            "status": ArtworkStatus.PENDING.value
        }

    async def get_by_id(self, task_id: str) -> Optional[dict]:
        result = await self.db.prepare("SELECT * FROM artworks WHERE id = ?").bind(task_id).all()
        items = result.results.to_py()
        return items[0] if items else None

    async def update_to_generating(self, task_id: str, provider_task_id: str, facing_direction: Optional[str] = None) -> bool:
        if facing_direction:
            await self.db.prepare(
                "UPDATE artworks SET status = ?, provider_task_id = ?, facing_direction = ? WHERE id = ?"
            ).bind(ArtworkStatus.GENERATING.value, provider_task_id, facing_direction, task_id).run()
        else:
            await self.db.prepare(
                "UPDATE artworks SET status = ?, provider_task_id = ? WHERE id = ?"
            ).bind(ArtworkStatus.GENERATING.value, provider_task_id, task_id).run()
        return True

    async def update_to_completed(self, task_id: str, video_url: str) -> bool:
        await self.db.prepare(
            "UPDATE artworks SET status = ?, video_url = ? WHERE id = ?"
        ).bind(ArtworkStatus.COMPLETED.value, video_url, task_id).run()
        return True

    async def update_to_failed(self, task_id: str) -> bool:
        await self.db.prepare(
            "UPDATE artworks SET status = ? WHERE id = ?"
        ).bind(ArtworkStatus.FAILED.value, task_id).run()
        return True

    async def get_all_generating(self, room_id: str) -> List[dict]:
        result = await self.db.prepare(f"SELECT * FROM artworks WHERE status = '{ArtworkStatus.GENERATING.value}' AND room_id = ?").bind(room_id).all()
        return result.results.to_py()

    async def get_all_completed(self, room_id: str) -> List[dict]:
        result = await self.db.prepare(
            f"SELECT * FROM artworks WHERE (status = '{ArtworkStatus.COMPLETED.value}' OR status = 'ready') AND room_id = ? AND hidden = 0 ORDER BY created_at DESC"
        ).bind(room_id).all()
        return result.results.to_py()

    async def get_all_rooms(self) -> List[dict]:
        result = await self.db.prepare(
            "SELECT room_id, COUNT(*) as count FROM artworks GROUP BY room_id ORDER BY room_id"
        ).all()
        return result.results.to_py()

    async def get_artworks_by_room(self, room_id: str) -> List[dict]:
        result = await self.db.prepare(
            "SELECT * FROM artworks WHERE room_id = ? ORDER BY created_at DESC"
        ).bind(room_id).all()
        return result.results.to_py()

    async def set_hidden(self, artwork_id: str, hidden: bool) -> bool:
        await self.db.prepare(
            "UPDATE artworks SET hidden = ? WHERE id = ?"
        ).bind(1 if hidden else 0, artwork_id).run()
        return True

    async def delete_artwork(self, artwork_id: str) -> Optional[dict]:
        """Returns the artwork before deletion (for R2 cleanup)."""
        result = await self.db.prepare("SELECT * FROM artworks WHERE id = ?").bind(artwork_id).all()
        items = result.results.to_py()
        if not items:
            return None
        await self.db.prepare("DELETE FROM artworks WHERE id = ?").bind(artwork_id).run()
        return items[0]


class AdminRepository:
    def __init__(self, db):
        self.db = db

    @staticmethod
    def _hash_password(password: str) -> str:
        salt = os.urandom(16).hex()
        key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260000)
        return f"{salt}${key.hex()}"

    @staticmethod
    def _verify_password(password: str, stored_hash: str) -> bool:
        try:
            salt, key_hex = stored_hash.split("$", 1)
            key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260000)
            return hmac.compare_digest(key.hex(), key_hex)
        except Exception:
            return False

    async def get_by_username(self, username: str) -> Optional[dict]:
        result = await self.db.prepare(
            "SELECT * FROM admins WHERE username = ?"
        ).bind(username).all()
        items = result.results.to_py()
        return items[0] if items else None

    async def verify_credentials(self, username: str, password: str) -> Optional[dict]:
        admin = await self.get_by_username(username)
        if not admin:
            return None
        if not self._verify_password(password, admin["password_hash"]):
            return None
        return admin