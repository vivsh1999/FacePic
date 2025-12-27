"""Person-related API endpoints."""
from fastapi import APIRouter

router = APIRouter(prefix="/api/persons", tags=["persons"])

# All person endpoints have been migrated to the Hono backend.
# This file is kept to avoid import errors but contains no endpoints.



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
