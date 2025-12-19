"""Image-related API endpoints."""
import os
import uuid
import json
import numpy as np
from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks, Form
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
    UploadWithFacesResponse,
    DetectedFaceInfo,
    UploadAndProcessResponse,
    DuplicatesResponse,
    DuplicateGroup,
    DuplicateImage,
    DeleteDuplicatesRequest,
    DeleteDuplicatesResponse,
)
from ..services import image_service, face_service
from ..services.encoding_utils import encoding_to_bytes
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
        "faces": image.faces,
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


@router.post("/upload-and-process", response_model=UploadAndProcessResponse)
async def upload_and_process_background(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Upload images and start background face detection processing.
    
    This endpoint quickly saves images and returns immediately,
    while face detection runs in the background using InsightFace.
    """
    uploaded = []
    uploaded_ids = []
    errors = []
    
    for file in files:
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
            
            # Create document with processed=0 (pending)
            image_doc = ImageDocument(
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
            
            # Insert into MongoDB
            result = await db.images.insert_one(image_doc.to_dict())
            image_id = str(result.inserted_id)
            image_doc.id = image_id
            
            uploaded.append(_image_to_response(image_doc, 0))
            uploaded_ids.append(image_id)
            
        except Exception as e:
            errors.append(f"Failed to upload {file.filename}: {str(e)}")
    
    # Start background processing if any images were uploaded
    task_id = None
    if uploaded_ids:
        task_id = str(uuid.uuid4())
        background_tasks_status[task_id] = {
            "task_id": task_id,
            "status": "pending",
            "progress": 0,
            "total": len(uploaded_ids),
            "processed": 0,
            "faces_detected": 0,
            "persons_created": 0,
            "errors": [],
            "completed_at": None,
        }
        background_tasks.add_task(_process_images_background, task_id, uploaded_ids)
    
    return UploadAndProcessResponse(
        uploaded=len(uploaded),
        failed=len(errors),
        images=uploaded,
        task_id=task_id,
        errors=errors,
    )


@router.post("/upload-server-detect", response_model=UploadWithFacesResponse)
async def upload_images_server_detect(
    files: List[UploadFile] = File(...),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Upload images with server-side face detection using InsightFace.
    
    This endpoint performs fast, accurate face detection on the server
    using InsightFace with ArcFace embeddings (512-dimensional).
    """
    from ..services import insightface_service
    
    uploaded = []
    errors = []
    total_faces = 0
    new_face_ids = []
    
    for file in files:
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
                processed=1,  # Already processed
            )
            
            # Insert into MongoDB
            result = await db.images.insert_one(image_doc.to_dict())
            image_id = str(result.inserted_id)
            image_doc.id = image_id
            
            # Detect faces using InsightFace
            detected_faces = insightface_service.detect_faces(filepath)
            
            image_face_ids = []
            for bbox, encoding in detected_faces:
                top, right, bottom, left = bbox
                # Convert numpy.int64 to Python int for MongoDB serialization
                top, right, bottom, left = int(top), int(right), int(bottom), int(left)
                
                # Create face document
                face_doc_data = {
                    "image_id": image_id,
                    "bbox_top": top,
                    "bbox_right": right,
                    "bbox_bottom": bottom,
                    "bbox_left": left,
                    "encoding": insightface_service.encoding_to_bytes(encoding),
                    "created_at": datetime.utcnow(),
                }
                
                face_result = await db.faces.insert_one(face_doc_data)
                face_id = str(face_result.inserted_id)
                image_face_ids.append(face_result.inserted_id)
                
                # Create face thumbnail
                face_thumbnail_path = image_service.create_face_thumbnail(
                    filepath,
                    {"top": top, "right": right, "bottom": bottom, "left": left},
                    face_id,
                )
                
                # Update face with thumbnail path
                await db.faces.update_one(
                    {"_id": face_result.inserted_id},
                    {"$set": {"thumbnail_path": face_thumbnail_path}}
                )
                
                new_face_ids.append(face_id)
                total_faces += 1
            
            # Update image with faces
            await db.images.update_one(
                {"_id": result.inserted_id},
                {"$set": {"faces": image_face_ids}}
            )
            image_doc.faces = [str(fid) for fid in image_face_ids]
            
            uploaded.append(_image_to_response(image_doc, len(detected_faces)))
            
        except Exception as e:
            errors.append(f"Failed to upload {file.filename}: {str(e)}")
    
    # Cluster new faces into persons
    persons_created = 0
    detected_faces_info: List[DetectedFaceInfo] = []
    
    if new_face_ids:
        clustering_stats = await cluster_faces(db, new_face_ids)
        persons_created = clustering_stats.get("new_persons_created", 0)
        
        # Fetch face details with person info
        for face_id in new_face_ids:
            face_doc = await db.faces.find_one({"_id": to_object_id(face_id)})
            if face_doc:
                person_id = face_doc.get("person_id")
                person_name = None
                is_new_person = False
                
                if person_id:
                    person_doc = await db.persons.find_one({"_id": to_object_id(person_id)})
                    if person_doc:
                        person_name = person_doc.get("name")
                        is_new_person = person_name is None or person_name == ""
                
                thumbnail_url = f"/api/images/faces/{face_id}/thumbnail" if face_doc.get("thumbnail_path") else ""
                
                detected_faces_info.append(DetectedFaceInfo(
                    face_id=face_id,
                    thumbnail_url=thumbnail_url,
                    person_id=person_id or "",
                    person_name=person_name,
                    is_new_person=is_new_person,
                    image_id=face_doc.get("image_id", ""),
                ))
    
    return UploadWithFacesResponse(
        uploaded=len(uploaded),
        failed=len(errors),
        images=uploaded,
        faces_detected=total_faces,
        persons_created=persons_created,
        detected_faces=detected_faces_info,
        errors=errors,
    )


@router.post("/upload-with-faces", response_model=UploadWithFacesResponse)
async def upload_images_with_faces(
    files: List[UploadFile] = File(...),
    face_data: str = Form(...),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Upload images with pre-detected face data from client-side face detection.
    
    This endpoint receives images along with face bounding boxes and encodings
    that were detected client-side using face-api.js, avoiding expensive 
    server-side face detection.
    """
    uploaded = []
    errors = []
    total_faces = 0
    new_face_ids = []
    
    # Parse face data JSON
    try:
        face_data_list = json.loads(face_data)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid face_data JSON: {str(e)}")
    
    if len(face_data_list) != len(files):
        raise HTTPException(
            status_code=400, 
            detail=f"Mismatch: {len(files)} files but {len(face_data_list)} face data entries"
        )
    
    for file, file_face_data in zip(files, face_data_list):
        # Validate file type
        if not image_service.is_valid_image(file.filename):
            errors.append(f"Invalid file type: {file.filename}")
            continue
        
        try:
            # Save the file
            filepath, unique_filename, file_size = await image_service.save_upload_file(file)
            
            # Get image dimensions from face data or from file
            width = file_face_data.get("width") or 0
            height = file_face_data.get("height") or 0
            if not width or not height:
                width, height = image_service.get_image_dimensions(filepath)
            
            mime_type = image_service.get_mime_type(filepath)
            
            # Create thumbnail
            thumbnail_path = image_service.create_image_thumbnail(filepath, unique_filename)
            
            # Create image document
            image_doc = ImageDocument(
                filename=unique_filename,
                original_filename=file.filename,
                filepath=filepath,
                thumbnail_path=thumbnail_path,
                width=width,
                height=height,
                file_size=file_size,
                mime_type=mime_type,
                processed=1,  # Already processed on client
            )
            
            # Insert image into MongoDB
            result = await db.images.insert_one(image_doc.to_dict())
            image_id = str(result.inserted_id)
            image_doc.id = image_id
            
            # Process faces from client data
            faces_in_image = file_face_data.get("faces", [])
            image_face_ids = []
            for face_data_item in faces_in_image:
                bbox = face_data_item.get("bbox", {})
                encoding_list = face_data_item.get("encoding", [])
                
                # Convert encoding list to bytes for storage
                encoding_array = np.array(encoding_list, dtype=np.float64)
                encoding_bytes = encoding_array.tobytes()
                
                # Create face document
                face_doc_data = {
                    "image_id": image_id,
                    "bbox_top": bbox.get("top", 0),
                    "bbox_right": bbox.get("right", 0),
                    "bbox_bottom": bbox.get("bottom", 0),
                    "bbox_left": bbox.get("left", 0),
                    "encoding": encoding_bytes,
                    "created_at": datetime.utcnow(),
                }
                
                face_result = await db.faces.insert_one(face_doc_data)
                face_id = str(face_result.inserted_id)
                image_face_ids.append(face_result.inserted_id)
                
                # Create face thumbnail
                thumbnail_path = image_service.create_face_thumbnail(
                    filepath,
                    {"top": bbox.get("top", 0), "right": bbox.get("right", 0), 
                     "bottom": bbox.get("bottom", 0), "left": bbox.get("left", 0)},
                    face_id,
                )
                
                # Update face with thumbnail path
                await db.faces.update_one(
                    {"_id": face_result.inserted_id},
                    {"$set": {"thumbnail_path": thumbnail_path}}
                )
                
                new_face_ids.append(face_id)
                total_faces += 1
            
            # Update image with faces
            await db.images.update_one(
                {"_id": result.inserted_id},
                {"$set": {"faces": image_face_ids}}
            )
            image_doc.faces = [str(fid) for fid in image_face_ids]
            
            uploaded.append(_image_to_response(image_doc, len(faces_in_image)))
            
        except Exception as e:
            errors.append(f"Failed to upload {file.filename}: {str(e)}")
    
    # Cluster new faces into persons
    persons_created = 0
    detected_faces: List[DetectedFaceInfo] = []
    
    if new_face_ids:
        from ..services.clustering_service import cluster_faces
        clustering_stats = await cluster_faces(db, new_face_ids)
        persons_created = clustering_stats.get("new_persons_created", 0)
        
        # Fetch face details with person info
        for face_id in new_face_ids:
            face_doc = await db.faces.find_one({"_id": to_object_id(face_id)})
            if face_doc:
                person_id = face_doc.get("person_id")
                person_name = None
                is_new_person = False
                
                if person_id:
                    person_doc = await db.persons.find_one({"_id": to_object_id(person_id)})
                    if person_doc:
                        person_name = person_doc.get("name")
                        # Check if this is a new person (no name set)
                        is_new_person = person_name is None or person_name == ""
                
                thumbnail_url = f"/api/images/faces/{face_id}/thumbnail" if face_doc.get("thumbnail_path") else ""
                
                detected_faces.append(DetectedFaceInfo(
                    face_id=face_id,
                    thumbnail_url=thumbnail_url,
                    person_id=person_id or "",
                    person_name=person_name,
                    is_new_person=is_new_person,
                    image_id=face_doc.get("image_id", ""),
                ))
    
    return UploadWithFacesResponse(
        uploaded=len(uploaded),
        failed=len(errors),
        images=uploaded,
        faces_detected=total_faces,
        persons_created=persons_created,
        detected_faces=detected_faces,
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


@router.get("/duplicates", response_model=DuplicatesResponse)
async def find_duplicates(db: AsyncIOMotorDatabase = Depends(get_db)):
    """
    Find duplicate images based on file hash.
    
    Returns groups of images that are exact duplicates.
    """
    from collections import defaultdict
    
    # Get all images
    cursor = db.images.find({})
    images = await cursor.to_list(length=10000)
    
    # Group by file hash
    hash_groups: dict = defaultdict(list)
    
    for doc in images:
        image = image_from_doc(doc)
        if image.filepath and os.path.exists(image.filepath):
            try:
                file_hash = image_service.calculate_file_hash(image.filepath)
                hash_groups[file_hash].append(DuplicateImage(
                    id=image.id,
                    filename=image.filename,
                    original_filename=image.original_filename,
                    thumbnail_url=f"/api/images/{image.id}/thumbnail" if image.thumbnail_path else None,
                    file_size=image.file_size,
                    uploaded_at=image.uploaded_at,
                ))
            except Exception as e:
                print(f"Error hashing {image.filepath}: {e}")
    
    # Filter to only groups with duplicates (more than 1 image)
    duplicate_groups = [
        DuplicateGroup(hash=h, images=imgs)
        for h, imgs in hash_groups.items()
        if len(imgs) > 1
    ]
    
    # Sort groups by number of duplicates (descending)
    duplicate_groups.sort(key=lambda g: len(g.images), reverse=True)
    
    # Count total duplicates (excluding one original per group)
    total_duplicates = sum(len(g.images) - 1 for g in duplicate_groups)
    
    return DuplicatesResponse(
        total_groups=len(duplicate_groups),
        total_duplicates=total_duplicates,
        groups=duplicate_groups,
    )


@router.post("/duplicates/delete", response_model=DeleteDuplicatesResponse)
async def delete_duplicates(
    request: DeleteDuplicatesRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Delete specified duplicate images.
    
    Also removes associated faces and their thumbnails.
    """
    deleted = 0
    errors = []
    
    for image_id in request.image_ids:
        oid = to_object_id(image_id)
        if not oid:
            errors.append(f"Invalid image ID: {image_id}")
            continue
        
        doc = await db.images.find_one({"_id": oid})
        if not doc:
            errors.append(f"Image not found: {image_id}")
            continue
        
        image = image_from_doc(doc)
        
        try:
            # Delete associated faces and their thumbnails
            faces_cursor = db.faces.find({"image_id": image_id})
            faces = await faces_cursor.to_list(length=1000)
            
            for face in faces:
                if face.get("thumbnail_path"):
                    image_service.delete_face_thumbnail(face["thumbnail_path"])
            
            await db.faces.delete_many({"image_id": image_id})
            
            # Delete image files
            image_service.delete_image_files(image.filepath, image.thumbnail_path)
            
            # Delete image document
            await db.images.delete_one({"_id": oid})
            
            deleted += 1
        except Exception as e:
            errors.append(f"Failed to delete {image_id}: {str(e)}")
    
    return DeleteDuplicatesResponse(deleted=deleted, errors=errors)


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


@router.post("/{image_id}/reprocess", response_model=UploadWithFacesResponse)
async def reprocess_image(
    image_id: str,
    face_data: str = Form(...),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Reprocess an existing image with new face data from client-side detection.
    Deletes existing faces and creates new ones from the provided face data.
    """
    oid = to_object_id(image_id)
    if not oid:
        raise HTTPException(status_code=400, detail="Invalid image ID")
    
    doc = await db.images.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Image not found")
    
    image = image_from_doc(doc)
    errors = []
    new_face_ids = []
    
    try:
        # Parse face data
        face_data_parsed = json.loads(face_data)
        faces_list = face_data_parsed.get("faces", [])
        
        # Delete existing face thumbnails
        faces_cursor = db.faces.find({"image_id": image_id})
        existing_faces = await faces_cursor.to_list(length=1000)
        for face in existing_faces:
            if face.get("thumbnail_path"):
                image_service.delete_face_thumbnail(face["thumbnail_path"])
        
        # Delete existing faces from database
        await db.faces.delete_many({"image_id": image_id})
        
        # Process new faces from client data
        image_face_ids = []
        for face_data_item in faces_list:
            bbox = face_data_item.get("bbox", {})
            encoding_list = face_data_item.get("encoding", [])
            
            # Convert encoding list to bytes for storage
            encoding_array = np.array(encoding_list, dtype=np.float64)
            encoding_bytes = encoding_array.tobytes()
            
            # Create face document
            face_doc_data = {
                "image_id": image_id,
                "bbox_top": bbox.get("top", 0),
                "bbox_right": bbox.get("right", 0),
                "bbox_bottom": bbox.get("bottom", 0),
                "bbox_left": bbox.get("left", 0),
                "encoding": encoding_bytes,
                "created_at": datetime.utcnow(),
            }
            
            face_result = await db.faces.insert_one(face_doc_data)
            face_id = str(face_result.inserted_id)
            image_face_ids.append(face_result.inserted_id)
            
            # Create face thumbnail
            thumbnail_path = image_service.create_face_thumbnail(
                image.filepath,
                {"top": bbox.get("top", 0), "right": bbox.get("right", 0), 
                 "bottom": bbox.get("bottom", 0), "left": bbox.get("left", 0)},
                face_id,
            )
            
            # Update face with thumbnail path
            await db.faces.update_one(
                {"_id": face_result.inserted_id},
                {"$set": {"thumbnail_path": thumbnail_path}}
            )
            
            new_face_ids.append(face_id)
        
        # Update image with faces
        await db.images.update_one(
            {"_id": oid},
            {"$set": {"faces": image_face_ids, "processed": 1}}
        )
        image.faces = [str(fid) for fid in image_face_ids]
        image.processed = 1
                {"_id": face_result.inserted_id},
                {"$set": {"thumbnail_path": thumbnail_path}}
            )
            
            new_face_ids.append(face_id)
        
        # Update image processed status
        await db.images.update_one(
            {"_id": oid},
            {"$set": {"processed": 1}}
        )
        
    except Exception as e:
        errors.append(f"Failed to reprocess: {str(e)}")
    
    # Cluster new faces into persons
    persons_created = 0
    detected_faces: List[DetectedFaceInfo] = []
    
    if new_face_ids:
        clustering_stats = await cluster_faces(db, new_face_ids)
        persons_created = clustering_stats.get("new_persons_created", 0)
        
        # Fetch face details with person info
        for face_id in new_face_ids:
            face_doc = await db.faces.find_one({"_id": to_object_id(face_id)})
            if face_doc:
                person_id = face_doc.get("person_id")
                person_name = None
                is_new_person = False
                
                if person_id:
                    person_doc = await db.persons.find_one({"_id": to_object_id(person_id)})
                    if person_doc:
                        person_name = person_doc.get("name")
                        is_new_person = person_name is None or person_name == ""
                
                thumbnail_url = f"/api/images/faces/{face_id}/thumbnail" if face_doc.get("thumbnail_path") else ""
                
                detected_faces.append(DetectedFaceInfo(
                    face_id=face_id,
                    thumbnail_url=thumbnail_url,
                    person_id=person_id or "",
                    person_name=person_name,
                    is_new_person=is_new_person,
                    image_id=image_id,
                ))
    
    # Get updated face count
    face_count = await db.faces.count_documents({"image_id": image_id})
    
    return UploadWithFacesResponse(
        uploaded=1,
        failed=len(errors),
        images=[_image_to_response(image, face_count)],
        faces_detected=len(new_face_ids),
        persons_created=persons_created,
        detected_faces=detected_faces,
        errors=errors,
    )


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
        image_face_ids = []
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
                image_face_ids.append(result.inserted_id)
                
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
            
            # Mark image as processed and update faces
            await db.images.update_one(
                {"_id": to_object_id(image.id)},
                {"$set": {"processed": 1, "faces": image_face_ids}}
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
            image_face_ids = []
            
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
                    image_face_ids.append(result.inserted_id)
                    
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
                    {"$set": {"processed": 1, "faces": image_face_ids}}
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
