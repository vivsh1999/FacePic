"""Image-related API endpoints."""
import os
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..database import get_db, SessionLocal
from ..models import Image, Face
from ..schemas import (
    ImageResponse, 
    ImageDetail, 
    UploadResponse, 
    ProcessingResponse,
    ProcessingStatus,
    ProcessImagesRequest,
    BackgroundProcessingResponse,
    TaskStatusResponse,
)
from ..services import image_service, face_service
from ..services.clustering_service import cluster_faces
from ..config import get_settings

router = APIRouter(prefix="/api/images", tags=["images"])
settings = get_settings()

# In-memory task storage (for production, use Redis or database)
background_tasks_status: Dict[str, Dict[str, Any]] = {}


def _image_to_response(image: Image, request_base_url: str = "") -> dict:
    """Convert Image model to response dict."""
    return {
        "id": image.id,
        "filename": image.filename,
        "original_filename": image.original_filename,
        "thumbnail_url": f"/api/images/{image.id}/thumbnail" if image.thumbnail_path else None,
        "image_url": f"/api/images/{image.id}/file",
        "width": image.width,
        "height": image.height,
        "file_size": image.file_size,
        "uploaded_at": image.uploaded_at,
        "processed": image.processed,
        "face_count": len(image.faces),
    }


@router.post("/upload", response_model=UploadResponse)
async def upload_images(
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = None,
):
    """
    Upload multiple images.
    
    Images are saved and queued for face detection processing.
    """
    uploaded = []
    errors = []
    
    for file in files:
        # Validate file type
        if not image_service.is_valid_image(file.filename):
            errors.append(f"Invalid file type: {file.filename}")
            continue
        
        try:
            # Save the file
            filepath, unique_filename, file_size = await image_service.save_upload_file(file)
            
            # Get image dimensions
            width, height = image_service.get_image_dimensions(filepath)
            mime_type = image_service.get_mime_type(filepath)
            
            # Create thumbnail
            thumbnail_path = image_service.create_image_thumbnail(filepath, unique_filename)
            
            # Create database record
            db_image = Image(
                filename=unique_filename,
                original_filename=file.filename,
                filepath=filepath,
                thumbnail_path=thumbnail_path,
                width=width,
                height=height,
                file_size=file_size,
                mime_type=mime_type,
                processed=0,  # Pending processing
            )
            db.add(db_image)
            db.commit()
            db.refresh(db_image)
            
            uploaded.append(_image_to_response(db_image))
            
        except Exception as e:
            errors.append(f"Failed to upload {file.filename}: {str(e)}")
    
    return UploadResponse(
        uploaded=len(uploaded),
        failed=len(errors),
        images=uploaded,
        errors=errors,
    )


@router.get("", response_model=List[ImageResponse])
async def list_images(
    skip: int = 0,
    limit: int = 50,
    processed: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """
    List all uploaded images.
    
    - **skip**: Number of records to skip (pagination)
    - **limit**: Maximum number of records to return
    - **processed**: Filter by processing status (0=pending, 1=done, -1=failed)
    """
    query = db.query(Image)
    
    if processed is not None:
        query = query.filter(Image.processed == processed)
    
    images = query.order_by(Image.uploaded_at.desc()).offset(skip).limit(limit).all()
    
    return [_image_to_response(img) for img in images]


@router.get("/status", response_model=ProcessingStatus)
async def get_processing_status(db: Session = Depends(get_db)):
    """Get the current processing status."""
    total = db.query(Image).count()
    processed = db.query(Image).filter(Image.processed == 1).count()
    pending = db.query(Image).filter(Image.processed == 0).count()
    failed = db.query(Image).filter(Image.processed == -1).count()
    total_faces = db.query(Face).count()
    
    return ProcessingStatus(
        total_images=total,
        processed=processed,
        pending=pending,
        failed=failed,
        total_faces_detected=total_faces,
    )


@router.get("/{image_id}", response_model=ImageDetail)
async def get_image(image_id: int, db: Session = Depends(get_db)):
    """Get image details including detected faces."""
    image = db.query(Image).filter(Image.id == image_id).first()
    
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    
    response = _image_to_response(image)
    response["faces"] = [
        {
            "id": face.id,
            "bbox": face.bbox,
            "thumbnail_url": f"/api/images/faces/{face.id}/thumbnail" if face.thumbnail_path else None,
            "person_id": face.person_id,
            "image_id": face.image_id,
            "created_at": face.created_at,
        }
        for face in image.faces
    ]
    
    return response


@router.get("/{image_id}/file")
async def get_image_file(image_id: int, db: Session = Depends(get_db)):
    """Get the original image file."""
    image = db.query(Image).filter(Image.id == image_id).first()
    
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    
    if not os.path.exists(image.filepath):
        raise HTTPException(status_code=404, detail="Image file not found")
    
    return FileResponse(
        image.filepath,
        media_type=image.mime_type or "image/jpeg",
        filename=image.original_filename,
    )


@router.get("/{image_id}/thumbnail")
async def get_image_thumbnail(image_id: int, db: Session = Depends(get_db)):
    """Get the image thumbnail."""
    image = db.query(Image).filter(Image.id == image_id).first()
    
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    
    if not image.thumbnail_path or not os.path.exists(image.thumbnail_path):
        raise HTTPException(status_code=404, detail="Thumbnail not found")
    
    return FileResponse(image.thumbnail_path, media_type="image/jpeg")


@router.delete("/{image_id}")
async def delete_image(image_id: int, db: Session = Depends(get_db)):
    """Delete an image and its associated data."""
    image = db.query(Image).filter(Image.id == image_id).first()
    
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    
    # Delete face thumbnails
    for face in image.faces:
        if face.thumbnail_path:
            image_service.delete_face_thumbnail(face.thumbnail_path)
    
    # Delete image files
    image_service.delete_image_files(image.filepath, image.thumbnail_path)
    
    # Delete from database (cascades to faces)
    db.delete(image)
    db.commit()
    
    return {"message": "Image deleted successfully"}


@router.post("/process", response_model=ProcessingResponse)
async def process_images(
    request: ProcessImagesRequest = None,
    db: Session = Depends(get_db),
):
    """
    Process images for face detection.
    
    If no image_ids provided, processes all pending images.
    """
    image_ids = request.image_ids if request else None
    
    # Get images to process
    query = db.query(Image).filter(Image.processed == 0)
    if image_ids:
        query = query.filter(Image.id.in_(image_ids))
    
    images = query.all()
    
    processed_count = 0
    faces_detected = 0
    errors = []
    new_face_ids = []
    
    for image in images:
        try:
            # Detect faces
            detected = face_service.detect_faces(image.filepath)
            
            for bbox, encoding in detected:
                top, right, bottom, left = bbox
                
                # Create face record
                face = Face(
                    image_id=image.id,
                    bbox_top=top,
                    bbox_right=right,
                    bbox_bottom=bottom,
                    bbox_left=left,
                    encoding=face_service.encoding_to_bytes(encoding),
                )
                db.add(face)
                db.flush()  # Get the ID
                
                # Create face thumbnail
                face.thumbnail_path = image_service.create_face_thumbnail(
                    image.filepath,
                    {"top": top, "right": right, "bottom": bottom, "left": left},
                    face.id,
                )
                
                new_face_ids.append(face.id)
                faces_detected += 1
            
            image.processed = 1
            processed_count += 1
            
        except Exception as e:
            image.processed = -1
            errors.append(f"Failed to process {image.filename}: {str(e)}")
    
    db.commit()
    
    # Cluster new faces into persons
    persons_created = 0
    if new_face_ids:
        clustering_stats = cluster_faces(db, new_face_ids)
        persons_created = clustering_stats.get("new_persons_created", 0)
    
    return ProcessingResponse(
        processed=processed_count,
        faces_detected=faces_detected,
        persons_created=persons_created,
        errors=errors,
    )


def _process_images_background(task_id: str, image_ids: List[int]):
    """Background task to process images for face detection."""
    db = SessionLocal()
    try:
        # Update task status
        background_tasks_status[task_id]["status"] = "processing"
        
        images = db.query(Image).filter(Image.id.in_(image_ids)).all()
        total = len(images)
        
        background_tasks_status[task_id]["total"] = total
        
        processed_count = 0
        faces_detected = 0
        errors = []
        new_face_ids = []
        
        for i, image in enumerate(images):
            try:
                # Detect faces
                detected = face_service.detect_faces(image.filepath)
                
                for bbox, encoding in detected:
                    top, right, bottom, left = bbox
                    
                    face = Face(
                        image_id=image.id,
                        bbox_top=top,
                        bbox_right=right,
                        bbox_bottom=bottom,
                        bbox_left=left,
                        encoding=face_service.encoding_to_bytes(encoding),
                    )
                    db.add(face)
                    db.flush()
                    
                    face.thumbnail_path = image_service.create_face_thumbnail(
                        image.filepath,
                        {"top": top, "right": right, "bottom": bottom, "left": left},
                        face.id,
                    )
                    
                    new_face_ids.append(face.id)
                    faces_detected += 1
                
                image.processed = 1
                processed_count += 1
                
            except Exception as e:
                image.processed = -1
                errors.append(f"Failed to process {image.filename}: {str(e)}")
            
            # Update progress
            background_tasks_status[task_id]["progress"] = i + 1
            background_tasks_status[task_id]["processed"] = processed_count
            background_tasks_status[task_id]["faces_detected"] = faces_detected
            background_tasks_status[task_id]["errors"] = errors
            
            db.commit()
        
        # Cluster new faces
        persons_created = 0
        if new_face_ids:
            clustering_stats = cluster_faces(db, new_face_ids)
            persons_created = clustering_stats.get("new_persons_created", 0)
        
        # Mark task as completed
        background_tasks_status[task_id]["status"] = "completed"
        background_tasks_status[task_id]["persons_created"] = persons_created
        background_tasks_status[task_id]["completed_at"] = datetime.utcnow().isoformat()
        
    except Exception as e:
        background_tasks_status[task_id]["status"] = "failed"
        background_tasks_status[task_id]["errors"].append(str(e))
    finally:
        db.close()


@router.post("/process/background", response_model=BackgroundProcessingResponse)
async def process_images_background(
    background_tasks: BackgroundTasks,
    request: ProcessImagesRequest = None,
    db: Session = Depends(get_db),
):
    """
    Process images for face detection in the background.
    
    Returns immediately with a task_id that can be used to check progress.
    """
    image_ids = request.image_ids if request else None
    
    # Get images to process
    query = db.query(Image).filter(Image.processed == 0)
    if image_ids:
        query = query.filter(Image.id.in_(image_ids))
    
    images = query.all()
    
    if not images:
        raise HTTPException(status_code=400, detail="No images to process")
    
    # Create task
    task_id = str(uuid.uuid4())
    image_ids_to_process = [img.id for img in images]
    
    background_tasks_status[task_id] = {
        "task_id": task_id,
        "status": "pending",
        "progress": 0,
        "total": len(images),
        "processed": 0,
        "faces_detected": 0,
        "persons_created": 0,
        "errors": [],
        "completed_at": None,
    }
    
    # Add background task
    background_tasks.add_task(_process_images_background, task_id, image_ids_to_process)
    
    return BackgroundProcessingResponse(
        message="Processing started in background",
        task_id=task_id,
        image_count=len(images),
    )


@router.get("/process/status/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    """Get the status of a background processing task."""
    if task_id not in background_tasks_status:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = background_tasks_status[task_id]
    return TaskStatusResponse(
        task_id=task["task_id"],
        status=task["status"],
        progress=task["progress"],
        total=task["total"],
        processed=task["processed"],
        faces_detected=task["faces_detected"],
        persons_created=task["persons_created"],
        errors=task["errors"],
        completed_at=task["completed_at"],
    )


# Face thumbnail endpoint (convenience)
@router.get("/faces/{face_id}/thumbnail")
async def get_face_thumbnail(face_id: int, db: Session = Depends(get_db)):
    """Get a face thumbnail."""
    face = db.query(Face).filter(Face.id == face_id).first()
    
    if not face:
        raise HTTPException(status_code=404, detail="Face not found")
    
    if not face.thumbnail_path or not os.path.exists(face.thumbnail_path):
        raise HTTPException(status_code=404, detail="Face thumbnail not found")
    
    return FileResponse(face.thumbnail_path, media_type="image/jpeg")
