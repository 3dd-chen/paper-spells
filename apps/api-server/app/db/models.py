from sqlalchemy import Column, String, DateTime
from app.db.engine import Base
import uuid
from datetime import datetime, timezone


class Artwork(Base):
    __tablename__ = "artworks"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    image_path = Column(String, nullable=True)
    video_url = Column(String, nullable=True)
    status = Column(String, default="pending")  # pending | generating | completed | failed
    provider_task_id = Column(String, nullable=True)
    facing_direction = Column(String, nullable=True)  # left | right
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
