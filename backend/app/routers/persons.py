"""Person-related API endpoints."""
import os
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..database import get_db
from ..models import Person, Face, Image
from ..schemas import (
    PersonResponse,
    PersonDetail,
    PersonUpdate,
    PersonMergeRequest,
)
from ..services.clustering_service import merge_persons, recalculate_all_clusters

router = APIRouter(prefix="/api/persons", tags=["persons"])


def _person_to_response(person: Person, db: Session) -> dict:
    """Convert Person model to response dict."""
    # Get face count
    face_count = len(person.faces)
    
    # Get photo count (unique images)
    photo_count = len(set(face.image_id for face in person.faces))
    
    # Get thumbnail URL from representative face
    thumbnail_url = None
    if person.representative_face_id:
        face = db.query(Face).filter(Face.id == person.representative_face_id).first()
        if face and face.thumbnail_path:
            thumbnail_url = f"/api/faces/{face.id}/thumbnail"
    elif person.faces:
        # Fallback to first face
        first_face = person.faces[0]
        if first_face.thumbnail_path:
            thumbnail_url = f"/api/faces/{first_face.id}/thumbnail"
    
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
    db: Session = Depends(get_db),
):
    """
    List all detected persons.
    
    - **skip**: Number of records to skip
    - **limit**: Maximum number of records to return
    - **labeled**: Filter by labeled (True) or unlabeled (False) persons
    - **search**: Search by name
    """
    query = db.query(Person)
    
    if labeled is True:
        query = query.filter(Person.name.isnot(None))
    elif labeled is False:
        query = query.filter(Person.name.is_(None))
    
    if search:
        query = query.filter(Person.name.ilike(f"%{search}%"))
    
    # Order by face count (most photos first)
    persons = query.order_by(Person.created_at.desc()).offset(skip).limit(limit).all()
    
    return [_person_to_response(p, db) for p in persons]


@router.get("/{person_id}", response_model=PersonDetail)
async def get_person(person_id: int, db: Session = Depends(get_db)):
    """Get person details including all their faces."""
    person = db.query(Person).filter(Person.id == person_id).first()
    
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    
    response = _person_to_response(person, db)
    response["faces"] = [
        {
            "id": face.id,
            "bbox": face.bbox,
            "thumbnail_url": f"/api/faces/{face.id}/thumbnail" if face.thumbnail_path else None,
            "person_id": face.person_id,
            "image_id": face.image_id,
            "created_at": face.created_at,
        }
        for face in person.faces
    ]
    
    return response


@router.put("/{person_id}", response_model=PersonResponse)
async def update_person(
    person_id: int,
    update: PersonUpdate,
    db: Session = Depends(get_db),
):
    """Update a person's name/label."""
    person = db.query(Person).filter(Person.id == person_id).first()
    
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    
    if update.name is not None:
        person.name = update.name if update.name.strip() else None
    
    db.commit()
    db.refresh(person)
    
    return _person_to_response(person, db)


@router.delete("/{person_id}")
async def delete_person(person_id: int, db: Session = Depends(get_db)):
    """
    Delete a person.
    
    Their faces will become unassigned and may be re-clustered.
    """
    person = db.query(Person).filter(Person.id == person_id).first()
    
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    
    # Unassign all faces
    for face in person.faces:
        face.person_id = None
    
    db.delete(person)
    db.commit()
    
    return {"message": "Person deleted successfully"}


@router.get("/{person_id}/photos")
async def get_person_photos(
    person_id: int,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """Get all photos containing a specific person."""
    person = db.query(Person).filter(Person.id == person_id).first()
    
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    
    # Get unique images where this person appears
    image_ids = list(set(face.image_id for face in person.faces))
    
    images = (
        db.query(Image)
        .filter(Image.id.in_(image_ids))
        .order_by(Image.uploaded_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    
    return {
        "person": _person_to_response(person, db),
        "total_photos": len(image_ids),
        "photos": [
            {
                "id": img.id,
                "filename": img.filename,
                "original_filename": img.original_filename,
                "thumbnail_url": f"/api/images/{img.id}/thumbnail" if img.thumbnail_path else None,
                "image_url": f"/api/images/{img.id}/file",
                "width": img.width,
                "height": img.height,
                "uploaded_at": img.uploaded_at,
                # Include face info for this person in this image
                "faces": [
                    {
                        "id": face.id,
                        "bbox": face.bbox,
                    }
                    for face in img.faces
                    if face.person_id == person_id
                ],
            }
            for img in images
        ],
    }


@router.post("/merge")
async def merge_person_clusters(
    request: PersonMergeRequest,
    db: Session = Depends(get_db),
):
    """
    Merge two person clusters.
    
    All faces from source_person_id are moved to target_person_id.
    The source person is then deleted.
    """
    if request.source_person_id == request.target_person_id:
        raise HTTPException(
            status_code=400, 
            detail="Source and target person IDs must be different"
        )
    
    success = merge_persons(db, request.source_person_id, request.target_person_id)
    
    if not success:
        raise HTTPException(
            status_code=404,
            detail="One or both persons not found"
        )
    
    # Get updated target person
    target = db.query(Person).filter(Person.id == request.target_person_id).first()
    
    return {
        "message": "Persons merged successfully",
        "person": _person_to_response(target, db) if target else None,
    }


@router.post("/recluster")
async def recluster_all_faces(db: Session = Depends(get_db)):
    """
    Recalculate all face clusters from scratch.
    
    Warning: This will remove all existing person assignments and names!
    """
    stats = recalculate_all_clusters(db)
    
    return {
        "message": "Reclustering complete",
        "stats": stats,
    }


@router.get("/{person_id}/thumbnail")
async def get_person_thumbnail(person_id: int, db: Session = Depends(get_db)):
    """Get the representative face thumbnail for a person."""
    person = db.query(Person).filter(Person.id == person_id).first()
    
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    
    # Try representative face first
    face = None
    if person.representative_face_id:
        face = db.query(Face).filter(Face.id == person.representative_face_id).first()
    
    # Fallback to first face
    if not face and person.faces:
        face = person.faces[0]
    
    if not face or not face.thumbnail_path:
        raise HTTPException(status_code=404, detail="No thumbnail available")
    
    if not os.path.exists(face.thumbnail_path):
        raise HTTPException(status_code=404, detail="Thumbnail file not found")
    
    return FileResponse(face.thumbnail_path, media_type="image/jpeg")
