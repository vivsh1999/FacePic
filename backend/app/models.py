"""MongoDB document models using Pydantic."""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from bson import ObjectId


class PyObjectId(str):
    """Custom type for MongoDB ObjectId."""
    
    @classmethod
    def __get_validators__(cls):
        yield cls.validate
    
    @classmethod
    def validate(cls, v):
        if isinstance(v, ObjectId):
            return str(v)
        if isinstance(v, str) and ObjectId.is_valid(v):
            return v
        raise ValueError("Invalid ObjectId")


class BoundingBox(BaseModel):
    """Face bounding box coordinates."""
    top: int
    right: int
    bottom: int
    left: int


class FolderDocument(BaseModel):
    """Model for storing folder structure."""
    
    id: Optional[str] = Field(default=None, alias="_id")
    name: str
    parent_id: Optional[str] = None
    path: str  # Materialized path (e.g., "/Vacations/2023")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str}
    
    def to_dict(self) -> dict:
        """Convert to dictionary for MongoDB insert."""
        data = self.model_dump(by_alias=True, exclude={"id"})
        return data


class ImageDocument(BaseModel):
    """Model for storing uploaded images."""
    
    id: Optional[str] = Field(default=None, alias="_id")
    filename: str
    original_filename: str
    filepath: str
    thumbnail_path: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    file_size: Optional[int] = None  # in bytes
    mime_type: Optional[str] = None
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)
    processed: int = 0  # 0: pending, 1: processed, -1: failed
    is_uploaded: bool = Field(default=True) # Whether the file is uploaded to R2
    relative_path: Optional[str] = None # Path relative to import directory, for re-uploading
    metadata: Dict[str, Any] = Field(default_factory=dict)  # EXIF and other metadata
    folder_id: Optional[str] = None  # Reference to FolderDocument
    faces: List[PyObjectId] = Field(default_factory=list, alias="faces")  # Redundant list of face IDs
    
    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str}
    
    def to_dict(self) -> dict:
        """Convert to dictionary for MongoDB insert."""
        data = self.model_dump(by_alias=True, exclude={"id"})
        # Convert string IDs back to ObjectIds for MongoDB
        if data.get("folder_id") and isinstance(data["folder_id"], str):
            try:
                data["folder_id"] = ObjectId(data["folder_id"])
            except:
                pass
        if data.get("faces"):
            converted_ids = []
            for fid in data["faces"]:
                if isinstance(fid, str):
                    try:
                        converted_ids.append(ObjectId(fid))
                    except:
                        converted_ids.append(fid)
                else:
                    converted_ids.append(fid)
            data["faces"] = converted_ids
        return data


class PersonDocument(BaseModel):
    """Model for storing identified persons (face clusters)."""
    
    id: Optional[str] = Field(default=None, alias="_id")
    name: Optional[str] = None  # User-assigned name, null if unlabeled
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    representative_face_id: Optional[str] = None  # Best face for thumbnail
    metadata: Dict[str, Any] = Field(default_factory=dict)  # Additional person info
    
    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str}
    
    @property
    def display_name(self) -> str:
        """Return name or a placeholder."""
        return self.name if self.name else f"Person {self.id[-6:] if self.id else 'Unknown'}"
    
    def to_dict(self) -> dict:
        """Convert to dictionary for MongoDB insert."""
        data = self.model_dump(by_alias=True, exclude={"id"})
        return data


class FaceDocument(BaseModel):
    """Model for storing detected faces."""
    
    id: Optional[str] = Field(default=None, alias="_id")
    image_id: str
    person_id: Optional[str] = None
    
    # Bounding box coordinates (top, right, bottom, left format from face_recognition)
    bbox_top: int
    bbox_right: int
    bbox_bottom: int
    bbox_left: int
    
    # Face encoding (128-dimensional vector stored as binary)
    encoding: Optional[bytes] = None
    
    # Thumbnail path for the cropped face
    thumbnail_path: Optional[str] = None
    
    # Confidence score if available
    confidence: Optional[float] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)  # Landmarks, pose, age, gender, etc.
    
    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str}
    
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
    
    def to_dict(self) -> dict:
        """Convert to dictionary for MongoDB insert."""
        data = self.model_dump(by_alias=True, exclude={"id"})
        return data


# Helper functions for document conversion
def image_from_doc(doc: dict) -> ImageDocument:
    """Create ImageDocument from MongoDB document."""
    if doc:
        doc["_id"] = str(doc["_id"])
    return ImageDocument(**doc) if doc else None


def person_from_doc(doc: dict) -> PersonDocument:
    """Create PersonDocument from MongoDB document."""
    if doc:
        doc["_id"] = str(doc["_id"])
    return PersonDocument(**doc) if doc else None


def face_from_doc(doc: dict) -> FaceDocument:
    """Create FaceDocument from MongoDB document."""
    if doc:
        doc["_id"] = str(doc["_id"])
    return FaceDocument(**doc) if doc else None

