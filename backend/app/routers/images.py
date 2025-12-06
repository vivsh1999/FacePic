"""Image-related API endpoints."""
import os
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.responses import FileResponse
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId

from ..database import get_db, get_sync_database, to_object_id
from ..models import ImageDocument, FaceDocument, image_from_doc, face_from_doc
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


def _image_to_response(image: ImageDocument, face_count: int = 0) -> dict:
    """Convert ImageDocument to response dict."""
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
        "face_count": face_count,
    }


@router.post("/upload", response_model=UploadResponse)
async def upload_images(
    files: List[UploadFile] = File(...),
    db: AsyncIOMotorDatabase = Depends(get_db),
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
            
            # Create document
            image_doc = ImageDocument(
                filename=unique_filename,
                original_filename=file.filename,
                filepath=filepath,
                thumbnail_path=thumbnail_path,
                width=width,
                height=height,
                file_size=file_size,
                mime_type=mime_type,
                processed=0,
            )
            
            # Insert into MongoDB
            result = await db.images.insert_one(image_doc.to_dict())
            image_doc.id = str(result.inserted_id)
            
            uploaded.append(_image_to_response(image_doc, 0))
            
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
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    List all uploaded images.
    """
    query = {}
    if processed is not None:
        query["processed"] = processed
    
    cursor = db.images.find(query).sort("uploaded_at", -1).skip(skip).limit(limit)
    images = await cursor.to_list(length=limit)
    
    result = []
    for doc in images:
        image = image_from_doc(doc)
        # Count faces for this image
        face_count = await db.faces.count_documents({"image_id": image.id})
        result.append(_image_to_response(image, face_count))
    
    return result


@router.get("/status", response_model=ProcessingStatus)
async def get_processing_status(db: AsyncIOMotorDatabase = Depends(get_db)):
    """Get the current processing status."""
    total = await db.images.count_documents({})
    processed = await db.images.count_documents({"processed": 1})
    pending = await db.images.count_documents({"processed": 0})
    failed = await db.images.count_documents({"processed": -1})
    total_faces = await db.faces.count_documents({})
    
    return ProcessingStatus(
        total_images=total,
        processed=processed,
        pending=pending,
        failed=failed,
        total_faces_detected=total_faces,
    )


@router.get("/{image_id}", response_model=ImageDetail)
async def get_image(image_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Get image details including detected faces."""
    oid = to_object_id(image_id)
    if not oid:
        raise HTTPException(status_code=400, detail="Invalid image ID")
    
    doc = await db.images.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Image not found")
    
    image = image_from_doc(doc)
    
    # Get faces for this image
    faces_cursor = db.faces.find({"image_id": image_id})
    faces = await faces_cursor.to_list(length=1000)
    
    response = _image_to_response(image, len(faces))
    response["faces"] = [
        {
            "id": str(face["_id"]),
            "bbox": {
                "top": face["bbox_top"],
                "right": face["bbox_right"],
                "bottom": face["bbox_bottom"],
                "left": face["bbox_left"],
            },
            "thumbnail_url": f"/api/images/faces/{str(face['_id'])}/thumbnail" if face.get("thumbnail_path") else None,
            "person_id": face.get("person_id"),
            "image_id": face["image_id"],
            "created_at": face.get("created_at"),
        }
        for face in faces
    ]
    
    return response


@router.get("/{image_id}/file")
async def get_image_file(image_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Get the original image file."""
    oid = to_object_id(image_id)
    if not oid:
        raise HTTPException(status_code=400, detail="Invalid image ID")
    
    doc = await db.images.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Image not found")
    
    image = image_from_doc(doc)
    
    if not os.path.exists(image.filepath):
        raise HTTPException(status_code=404, detail="Image file not found")
    
    return FileResponse(
        image.filepath,
        media_type=image.mime_type or "image/jpeg",
        filename=image.original_filename,
    )


@router.get("/{image_id}/thumbnail")
async def get_image_thumbnail(image_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Get the image thumbnail."""
    oid = to_object_id(image_id)
    if not oid:
        raise HTTPException(status_code=400, detail="Invalid image ID")
    
    doc = await db.images.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Image not found")
    
    image = image_from_doc(doc)
    
    if not image.thumbnail_path or not os.path.exists(image.thumbnail_path):
        raise HTTPException(status_code=404, detail="Thumbnail not found")
    
    return FileResponse(image.thumbnail_path, media_type="image/jpeg")


@router.delete("/{image_id}")
async def delete_image(image_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Delete an image and its associated data."""
    oid = to_object_id(image_id)
    if not oid:
        raise HTTPException(status_code=400, detail="Invalid image ID")
    
    doc = await db.images.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Image not found")
    
    image = image_from_doc(doc)
    
    # Delete face thumbnails
    faces_cursor = db.faces.find({"image_id": image_id})
    faces = await faces_cursor.to_list(length=1000)
    for face in faces:
        if face.get("thumbnail_path"):
            image_service.delete_face_thumbnail(face["thumbnail_path"])
    
    # Delete faces from database
    await db.faces.delete_many({"image_id": image_id})
    
    # Delete image files
    image_service.delete_image_files(image.filepath, image.thumbnail_path)
    
    # Delete image from database
    await db.images.delete_one({"_id": oid})
    
    return {"message": "Image deleted successfully"}


@router.post("/process", response_model=ProcessingResponse)
async def process_images(
    request: ProcessImagesRequest = None,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Process images for face detection.
    """
    image_ids = request.image_ids if request else None
    
    # Get images to process
    query = {"processed": 0}
    if image_ids:
        query["_id"] = {"$in": [to_object_id(id) for id in image_ids if to_object_id(id)]}
    
    cursor = db.images.find(query)
    images = await cursor.to_list(length=1000)
    
    processed_count = 0
    faces_detected = 0
    errors = []
    new_face_ids = []
    
    for doc in images:
        image = image_from_doc(doc)
        try:
            # Detect faces
            detected = face_service.detect_faces(image.filepath)
            
            for bbox, encoding in detected:
                top, right, bottom, left = bbox
                
                # Create face document
                face_doc = FaceDocument(
                    image_id=image.id,
                    bbox_top=top,
                    bbox_right=right,
                    bbox_bottom=bottom,
                    bbox_left=left,
                    encoding=face_service.encoding_to_bytes(encoding),
                )
                
                result = await db.faces.insert_one(face_doc.to_dict())
                face_id = str(result.inserted_id)
                
                # Create face thumbnail
                thumbnail_path = image_service.create_face_thumbnail(
                    image.filepath,
                    {"top": top, "right": right, "bottom": bottom, "left": left},
                    face_id,
                )
                
                # Update face with thumbnail path
                await db.faces.update_one(
                    {"_id": result.inserted_id},
                    {"$set": {"thumbnail_path": thumbnail_path}}
                )
                
                new_face_ids.append(face_id)
                faces_detected += 1
            
            # Mark image as processed
            await db.images.update_one(
                {"_id": to_object_id(image.id)},
                {"$set": {"processed": 1}}
            )
            processed_count += 1
            
        except Exception as e:
            await db.images.update_one(
                {"_id": to_object_id(image.id)},
                {"$set": {"processed": -1}}
            )
            errors.append(f"Failed to process {image.filename}: {str(e)}")
    
    # Cluster new faces into persons
    persons_created = 0
    if new_face_ids:
        clustering_stats = await cluster_faces(db, new_face_ids)
        persons_created = clustering_stats.get("new_persons_created", 0)
    
    return ProcessingResponse(
        processed=processed_count,
        faces_detected=faces_detected,
        persons_created=persons_created,
        errors=errors,
    )


def _process_images_background(task_id: str, image_ids: List[str]):
    """Background task to process images for face detection."""
    db = get_sync_database()
    try:
        # Update task status
        background_tasks_status[task_id]["status"] = "processing"
        
        # Get images
        images = list(db.images.find({"_id": {"$in": [ObjectId(id) for id in image_ids]}}))
        total = len(images)
        
        background_tasks_status[task_id]["total"] = total
        
        processed_count = 0
        faces_detected = 0
        errors = []
        new_face_ids = []
        
        for i, doc in enumerate(images):
            doc["_id"] = str(doc["_id"])
            image = image_from_doc(doc)
            
            try:
                # Detect faces
                detected = face_service.detect_faces(image.filepath)
                
                for bbox, encoding in detected:
                    top, right, bottom, left = bbox
                    
                    face_data = {
                        "image_id": image.id,
                        "bbox_top": top,
                        "bbox_right": right,
                        "bbox_bottom": bottom,
                        "bbox_left": left,
                        "encoding": face_service.encoding_to_bytes(encoding),
                        "created_at": datetime.utcnow(),
                    }
                    
                    result = db.faces.insert_one(face_data)
                    face_id = str(result.inserted_id)
                    
                    thumbnail_path = image_service.create_face_thumbnail(
                        image.filepath,
                        {"top": top, "right": right, "bottom": bottom, "left": left},
                        face_id,
                    )
                    
                    db.faces.update_one(
                        {"_id": result.inserted_id},
                        {"$set": {"thumbnail_path": thumbnail_path}}
                    )
                    
                    new_face_ids.append(face_id)
                    faces_detected += 1
                
                db.images.update_one(
                    {"_id": ObjectId(image.id)},
                    {"$set": {"processed": 1}}
                )
                processed_count += 1
                
            except Exception as e:
                db.images.update_one(
                    {"_id": ObjectId(image.id)},
                    {"$set": {"processed": -1}}
                )
                errors.append(f"Failed to process {image.filename}: {str(e)}")
            
            # Update progress
            background_tasks_status[task_id]["progress"] = i + 1
            background_tasks_status[task_id]["processed"] = processed_count
            background_tasks_status[task_id]["faces_detected"] = faces_detected
            background_tasks_status[task_id]["errors"] = errors
        
        # Cluster new faces (sync version)
        persons_created = 0
        if new_face_ids:
            from ..services.clustering_service import cluster_faces_sync
            clustering_stats = cluster_faces_sync(db, new_face_ids)
            persons_created = clustering_stats.get("new_persons_created", 0)
        
        # Mark task as completed
        background_tasks_status[task_id]["status"] = "completed"
        background_tasks_status[task_id]["persons_created"] = persons_created
        background_tasks_status[task_id]["completed_at"] = datetime.utcnow().isoformat()
        
    except Exception as e:
        background_tasks_status[task_id]["status"] = "failed"
        background_tasks_status[task_id]["errors"].append(str(e))


@router.post("/process/background", response_model=BackgroundProcessingResponse)
async def process_images_background(
    background_tasks: BackgroundTasks,
    request: ProcessImagesRequest = None,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Process images for face detection in the background.
    """
    image_ids = request.image_ids if request else None
    
    # Get images to process
    query = {"processed": 0}
    if image_ids:
        query["_id"] = {"$in": [to_object_id(id) for id in image_ids if to_object_id(id)]}
    
    cursor = db.images.find(query)
    images = await cursor.to_list(length=1000)
    
    if not images:
        raise HTTPException(status_code=400, detail="No images to process")
    
    # Create task
    task_id = str(uuid.uuid4())
    image_ids_to_process = [str(img["_id"]) for img in images]
    
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


@router.get("/faces/{face_id}/thumbnail")
async def get_face_thumbnail(face_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Get a face thumbnail."""
    oid = to_object_id(face_id)
    if not oid:
        raise HTTPException(status_code=400, detail="Invalid face ID")
    
    doc = await db.faces.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Face not found")
    
    face = face_from_doc(doc)
    
    if not face.thumbnail_path or not os.path.exists(face.thumbnail_path):
        raise HTTPException(status_code=404, detail="Face thumbnail not found")
    
    return FileResponse(face.thumbnail_path, media_type="image/jpeg")
