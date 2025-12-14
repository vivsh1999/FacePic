"""Person-related API endpoints."""
import os
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId

from ..database import get_db, to_object_id
from ..models import PersonDocument, person_from_doc, face_from_doc, image_from_doc
from ..schemas import (
    PersonResponse,
    PersonDetail,
    PersonUpdate,
    PersonMergeRequest,
)
from ..services.clustering_service import merge_persons, recalculate_all_clusters

router = APIRouter(prefix="/api/persons", tags=["persons"])


async def _person_to_response(person: PersonDocument, db: AsyncIOMotorDatabase) -> dict:
    """Convert PersonDocument to response dict."""
    # Get faces for this person
    faces_cursor = db.faces.find({"person_id": person.id})
    faces = await faces_cursor.to_list(length=10000)
    
    face_count = len(faces)
    photo_count = len(set(face["image_id"] for face in faces))
    
    # Get thumbnail URL from representative face
    thumbnail_url = None
    if person.representative_face_id:
        face = await db.faces.find_one({"_id": to_object_id(person.representative_face_id)})
        if face and face.get("thumbnail_path"):
            thumbnail_url = f"/api/images/faces/{person.representative_face_id}/thumbnail"
    elif faces:
        # Fallback to first face
        first_face = faces[0]
        if first_face.get("thumbnail_path"):
            thumbnail_url = f"/api/images/faces/{str(first_face['_id'])}/thumbnail"
    
    return {
        "id": person.id,
        "name": person.name,
        "display_name": person.display_name,
        "face_count": face_count,
        "photo_count": photo_count,
        "thumbnail_url": thumbnail_url,
        "created_at": person.created_at,
        "updated_at": person.updated_at,
    }


@router.get("", response_model=List[PersonResponse])
async def list_persons(
    skip: int = 0,
    limit: int = 50,
    labeled: Optional[bool] = None,
    search: Optional[str] = None,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    List all detected persons.
    """
    query = {}
    
    if labeled is True:
        query["name"] = {"$ne": None}
    elif labeled is False:
        query["name"] = None
    
    if search:
        query["name"] = {"$regex": search, "$options": "i"}
    
    # Sort: named persons first (name exists), then by created_at descending
    # We use aggregation pipeline for more control
    pipeline = [
        {"$match": query},
        {
            "$addFields": {
                "has_name": {"$cond": [{"$ifNull": ["$name", False]}, 1, 0]}
            }
        },
        {"$sort": {"has_name": -1, "created_at": -1}},
        {"$skip": skip},
        {"$limit": limit}
    ]
    
    cursor = db.persons.aggregate(pipeline)
    persons = await cursor.to_list(length=limit)
    
    result = []
    for doc in persons:
        person = person_from_doc(doc)
        result.append(await _person_to_response(person, db))
    
    return result


@router.get("/{person_id}", response_model=PersonDetail)
async def get_person(person_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Get person details including all their faces."""
    oid = to_object_id(person_id)
    if not oid:
        raise HTTPException(status_code=400, detail="Invalid person ID")
    
    doc = await db.persons.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Person not found")
    
    person = person_from_doc(doc)
    
    # Get faces
    faces_cursor = db.faces.find({"person_id": person_id})
    faces = await faces_cursor.to_list(length=10000)
    
    response = await _person_to_response(person, db)
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


@router.put("/{person_id}", response_model=PersonResponse)
async def update_person(
    person_id: str,
    update: PersonUpdate,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Update a person's name/label."""
    oid = to_object_id(person_id)
    if not oid:
        raise HTTPException(status_code=400, detail="Invalid person ID")
    
    doc = await db.persons.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Person not found")
    
    # Update name
    name = update.name.strip() if update.name and update.name.strip() else None
    await db.persons.update_one(
        {"_id": oid},
        {"$set": {"name": name, "updated_at": datetime.utcnow()}}
    )
    
    # Fetch updated document
    doc = await db.persons.find_one({"_id": oid})
    person = person_from_doc(doc)
    
    return await _person_to_response(person, db)


@router.delete("/{person_id}")
async def delete_person(person_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    """
    Delete a person.
    
    Their faces will become unassigned and may be re-clustered.
    """
    oid = to_object_id(person_id)
    if not oid:
        raise HTTPException(status_code=400, detail="Invalid person ID")
    
    doc = await db.persons.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Person not found")
    
    # Unassign all faces
    await db.faces.update_many(
        {"person_id": person_id},
        {"$set": {"person_id": None}}
    )
    
    # Delete person
    await db.persons.delete_one({"_id": oid})
    
    return {"message": "Person deleted successfully"}


@router.get("/{person_id}/photos")
async def get_person_photos(
    person_id: str,
    skip: int = 0,
    limit: int = 50,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Get all photos containing a specific person."""
    oid = to_object_id(person_id)
    if not oid:
        raise HTTPException(status_code=400, detail="Invalid person ID")
    
    doc = await db.persons.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Person not found")
    
    person = person_from_doc(doc)
    
    # Get unique image IDs for this person
    faces_cursor = db.faces.find({"person_id": person_id})
    faces = await faces_cursor.to_list(length=10000)
    
    image_ids = list(set(face["image_id"] for face in faces))
    total_photos = len(image_ids)
    
    # Get images with pagination
    paginated_ids = image_ids[skip:skip + limit]
    images_cursor = db.images.find({"_id": {"$in": [to_object_id(id) for id in paginated_ids]}})
    images = await images_cursor.to_list(length=limit)
    
    # Sort by uploaded_at
    images.sort(key=lambda x: x.get("uploaded_at", datetime.min), reverse=True)
    
    photos = []
    for img in images:
        image = image_from_doc(img)
        
        # Get faces for this person in this image
        person_faces = [f for f in faces if f["image_id"] == image.id]
        
        photos.append({
            "id": image.id,
            "filename": image.filename,
            "original_filename": image.original_filename,
            "thumbnail_url": f"/api/images/{image.id}/thumbnail" if image.thumbnail_path else None,
            "image_url": f"/api/images/{image.id}/file",
            "width": image.width,
            "height": image.height,
            "uploaded_at": image.uploaded_at,
            "faces": [
                {
                    "id": str(face["_id"]),
                    "bbox": {
                        "top": face["bbox_top"],
                        "right": face["bbox_right"],
                        "bottom": face["bbox_bottom"],
                        "left": face["bbox_left"],
                    },
                }
                for face in person_faces
            ],
        })
    
    return {
        "person": await _person_to_response(person, db),
        "total_photos": total_photos,
        "photos": photos,
    }


@router.post("/merge")
async def merge_person_clusters(
    request: PersonMergeRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Merge two person clusters.
    """
    if request.source_person_id == request.target_person_id:
        raise HTTPException(
            status_code=400, 
            detail="Source and target person IDs must be different"
        )
    
    success = await merge_persons(db, request.source_person_id, request.target_person_id)
    
    if not success:
        raise HTTPException(
            status_code=404,
            detail="One or both persons not found"
        )
    
    # Get updated target person
    doc = await db.persons.find_one({"_id": to_object_id(request.target_person_id)})
    
    if doc:
        person = person_from_doc(doc)
        return {
            "message": "Persons merged successfully",
            "person": await _person_to_response(person, db),
        }
    
    return {"message": "Persons merged successfully", "person": None}


@router.post("/recluster")
async def recluster_all_faces(db: AsyncIOMotorDatabase = Depends(get_db)):
    """
    Recalculate all face clusters from scratch.
    """
    stats = await recalculate_all_clusters(db)
    
    return {
        "message": "Reclustering complete",
        "stats": stats,
    }


@router.get("/{person_id}/thumbnail")
async def get_person_thumbnail(person_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Get the representative face thumbnail for a person."""
    oid = to_object_id(person_id)
    if not oid:
        raise HTTPException(status_code=400, detail="Invalid person ID")
    
    doc = await db.persons.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Person not found")
    
    person = person_from_doc(doc)
    
    # Try representative face first
    face = None
    if person.representative_face_id:
        face_doc = await db.faces.find_one({"_id": to_object_id(person.representative_face_id)})
        if face_doc:
            face = face_doc
    
    # Fallback to first face
    if not face:
        face = await db.faces.find_one({"person_id": person_id})
    
    if not face or not face.get("thumbnail_path"):
        raise HTTPException(status_code=404, detail="No thumbnail available")
    
    if not os.path.exists(face["thumbnail_path"]):
        raise HTTPException(status_code=404, detail="Thumbnail file not found")
    
    return FileResponse(face["thumbnail_path"], media_type="image/jpeg")
