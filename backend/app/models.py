"""SQLAlchemy ORM models."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey, LargeBinary, Text
from sqlalchemy.orm import relationship
from .database import Base


class Image(Base):
    """Model for storing uploaded images."""
    
    __tablename__ = "images"
    
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    filepath = Column(String(512), nullable=False, unique=True)
    thumbnail_path = Column(String(512), nullable=True)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    file_size = Column(Integer, nullable=True)  # in bytes
    mime_type = Column(String(100), nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    processed = Column(Integer, default=0)  # 0: pending, 1: processed, -1: failed
    
    # Relationships
    faces = relationship("Face", back_populates="image", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Image(id={self.id}, filename='{self.filename}')>"


class Person(Base):
    """Model for storing identified persons (face clusters)."""
    
    __tablename__ = "persons"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=True)  # User-assigned name, null if unlabeled
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    representative_face_id = Column(Integer, nullable=True)  # Best face for thumbnail
    
    # Relationships
    faces = relationship("Face", back_populates="person")
    
    @property
    def display_name(self) -> str:
        """Return name or a placeholder."""
        return self.name if self.name else f"Person {self.id}"
    
    @property
    def photo_count(self) -> int:
        """Number of photos this person appears in."""
        return len(set(face.image_id for face in self.faces))
    
    def __repr__(self):
        return f"<Person(id={self.id}, name='{self.name}')>"


class Face(Base):
    """Model for storing detected faces."""
    
    __tablename__ = "faces"
    
    id = Column(Integer, primary_key=True, index=True)
    image_id = Column(Integer, ForeignKey("images.id", ondelete="CASCADE"), nullable=False)
    person_id = Column(Integer, ForeignKey("persons.id", ondelete="SET NULL"), nullable=True)
    
    # Bounding box coordinates (top, right, bottom, left format from face_recognition)
    bbox_top = Column(Integer, nullable=False)
    bbox_right = Column(Integer, nullable=False)
    bbox_bottom = Column(Integer, nullable=False)
    bbox_left = Column(Integer, nullable=False)
    
    # Face encoding (128-dimensional vector stored as binary)
    encoding = Column(LargeBinary, nullable=True)
    
    # Thumbnail path for the cropped face
    thumbnail_path = Column(String(512), nullable=True)
    
    # Confidence score if available
    confidence = Column(Float, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    image = relationship("Image", back_populates="faces")
    person = relationship("Person", back_populates="faces")
    
    @property
    def bbox(self) -> dict:
        """Return bounding box as dictionary."""
        return {
            "top": self.bbox_top,
            "right": self.bbox_right,
            "bottom": self.bbox_bottom,
            "left": self.bbox_left,
        }
    
    @property
    def width(self) -> int:
        """Width of the face bounding box."""
        return self.bbox_right - self.bbox_left
    
    @property
    def height(self) -> int:
        """Height of the face bounding box."""
        return self.bbox_bottom - self.bbox_top
    
    def __repr__(self):
        return f"<Face(id={self.id}, image_id={self.image_id}, person_id={self.person_id})>"
