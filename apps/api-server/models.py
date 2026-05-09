from sqlalchemy import Column, String
from database import Base
import uuid

class Artwork(Base):
    __tablename__ = "artworks"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    image_url = Column(String, nullable=True)
    video_url = Column(String, nullable=True)
    status = Column(String, default="pending")  # pending, completed, failed
