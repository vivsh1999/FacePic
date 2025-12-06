"""Pydantic schemas for request/response validation."""
from datetime import datetime
from typing import Optional, List, Union
from pydantic import BaseModel, Field


# ============ Request Schemas ============

class ProcessImagesRequest(BaseModel):
    """Request body for processing images."""
    image_ids: Optional[List[str]] = None


# ============ Face Schemas ============

class BoundingBox(BaseModel):
    """Face bounding box coordinates."""
    top: int
    right: int
    bottom: int
    left: int


class FaceBase(BaseModel):
    """Base face schema."""
    bbox: BoundingBox
    thumbnail_path: Optional[str] = None


class FaceCreate(FaceBase):
    """Schema for creating a face."""
    image_id: str
    encoding: Optional[bytes] = None


class FaceResponse(FaceBase):
    """Schema for face in API responses."""
    id: str
    image_id: str
    person_id: Optional[str] = None
    thumbnail_url: Optional[str] = None
    created_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


# ============ Person Schemas ============

class PersonBase(BaseModel):
    """Base person schema."""
    name: Optional[str] = None


class PersonCreate(PersonBase):
    """Schema for creating a person."""
    pass


class PersonUpdate(BaseModel):
    """Schema for updating a person."""
    name: Optional[str] = None


class PersonResponse(PersonBase):
    """Schema for person in API responses."""
    id: str
    display_name: str
    photo_count: int
    face_count: int
    thumbnail_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class PersonDetail(PersonResponse):
    """Detailed person response with faces."""
    faces: List[FaceResponse] = []


class PersonMergeRequest(BaseModel):
    """Request to merge two persons."""
    source_person_id: str = Field(..., description="Person ID to merge from (will be deleted)")
    target_person_id: str = Field(..., description="Person ID to merge into (will be kept)")


# ============ Image Schemas ============

class ImageBase(BaseModel):
    """Base image schema."""
    filename: str
    original_filename: str


class ImageCreate(ImageBase):
    """Schema for creating an image record."""
    filepath: str
    thumbnail_path: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    file_size: Optional[int] = None
    mime_type: Optional[str] = None


class ImageResponse(ImageBase):
    """Schema for image in API responses."""
    id: str
    thumbnail_url: Optional[str] = None
    image_url: str
    width: Optional[int] = None
    height: Optional[int] = None
    file_size: Optional[int] = None
    uploaded_at: datetime
    processed: int
    face_count: int
    
    class Config:
        from_attributes = True


class ImageDetail(ImageResponse):
    """Detailed image response with faces."""
    faces: List[FaceResponse] = []


# ============ Upload Schemas ============

class UploadResponse(BaseModel):
    """Response after uploading images."""
    uploaded: int
    failed: int
    images: List[ImageResponse]
    errors: List[str] = []


# ============ Processing Schemas ============

class ProcessingStatus(BaseModel):
    """Status of face detection processing."""
    total_images: int
    processed: int
    pending: int
    failed: int
    total_faces_detected: int


class ProcessingRequest(BaseModel):
    """Request to process images."""
    image_ids: Optional[List[str]] = None  # If None, process all pending


class ProcessingResponse(BaseModel):
    """Response after processing images."""
    processed: int
    faces_detected: int
    persons_created: int
    errors: List[str] = []


class BackgroundProcessingResponse(BaseModel):
    """Response when processing is started in background."""
    message: str
    task_id: str
    image_count: int


class TaskStatusResponse(BaseModel):
    """Response for background task status."""
    task_id: str
    status: str  # pending, processing, completed, failed
    progress: int
    total: int
    processed: int
    faces_detected: int
    persons_created: int
    errors: List[str] = []
    completed_at: Optional[datetime] = None


# ============ Stats Schemas ============

class StatsResponse(BaseModel):
    """Overall statistics."""
    total_images: int
    total_faces: int
    total_persons: int
    labeled_persons: int
    unlabeled_persons: int
