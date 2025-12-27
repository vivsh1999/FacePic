"""Face clustering service for grouping similar faces."""
import numpy as np
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId

from ..models import PersonDocument, person_from_doc
from ..database import to_object_id
from ..config import get_settings
from .encoding_utils import bytes_to_encoding

settings = get_settings()


async def cluster_faces(db: AsyncIOMotorDatabase, face_ids: Optional[List[str]] = None) -> Dict[str, int]:
    """
    Cluster faces into person groups (async version).
    
    This function takes unassigned faces and either:
    1. Matches them to existing persons
    2. Creates new person clusters for unmatched faces
    """
    stats = {
        "matched_to_existing": 0,
        "new_persons_created": 0,
        "faces_processed": 0,
    }
    
    # Get faces to process
    query = {"person_id": None}
    if face_ids:
        query["_id"] = {"$in": [to_object_id(id) for id in face_ids if to_object_id(id)]}
    
    cursor = db.faces.find(query)
    unassigned_faces = await cursor.to_list(length=10000)
    
    if not unassigned_faces:
        return stats
    
    # Get all existing persons
    persons_cursor = db.persons.find()
    existing_persons = await persons_cursor.to_list(length=10000)
    
    # Build encoding lookup for existing persons
    person_encodings: Dict[str, List[np.ndarray]] = {}
    for person_doc in existing_persons:
        person_id = str(person_doc["_id"])
        faces_cursor = db.faces.find({"person_id": person_id})
        faces = await faces_cursor.to_list(length=1000)
        
        encodings = []
        for face in faces:
            if face.get("encoding"):
                encodings.append(bytes_to_encoding(face["encoding"]))
        if encodings:
            person_encodings[person_id] = encodings
    
    # Process each unassigned face
    for face in unassigned_faces:
        if not face.get("encoding"):
            continue
        
        face_encoding = bytes_to_encoding(face["encoding"])
        face_id = str(face["_id"])
        stats["faces_processed"] += 1
        
        # Determine tolerance based on encoding dimension
        # 512-dim = InsightFace (cosine distance), 128-dim = face-api.js (Euclidean)
        tolerance = settings.insightface_tolerance if len(face_encoding) == 512 else settings.face_recognition_tolerance
        
        # Try to find a matching person
        best_match = _find_matching_person(
            face_encoding, 
            person_encodings,
            tolerance
        )
        
        if best_match:
            person_id, distance = best_match
            
            # Update face with person_id
            await db.faces.update_one(
                {"_id": face["_id"]},
                {"$set": {"person_id": person_id}}
            )
            stats["matched_to_existing"] += 1
            
            # Add this encoding to the person's encodings for future matching
            if person_id not in person_encodings:
                person_encodings[person_id] = []
            person_encodings[person_id].append(face_encoding)
        else:
            # Create a new person for this face
            new_person = PersonDocument()
            result = await db.persons.insert_one(new_person.to_dict())
            new_person_id = str(result.inserted_id)
            
            # Update face with person_id
            await db.faces.update_one(
                {"_id": face["_id"]},
                {"$set": {"person_id": new_person_id}}
            )
            
            # Set representative face
            await db.persons.update_one(
                {"_id": result.inserted_id},
                {"$set": {"representative_face_id": face_id}}
            )
            
            # Add to our tracking dict
            person_encodings[new_person_id] = [face_encoding]
            
            stats["new_persons_created"] += 1
    
    return stats


def cluster_faces_sync(db, face_ids: Optional[List[str]] = None) -> Dict[str, int]:
    """
    Cluster faces into person groups (sync version for background tasks).
    """
    stats = {
        "matched_to_existing": 0,
        "new_persons_created": 0,
        "faces_processed": 0,
    }
    
    # Get faces to process
    query = {"person_id": None}
    if face_ids:
        query["_id"] = {"$in": [ObjectId(id) for id in face_ids if ObjectId.is_valid(id)]}
    
    unassigned_faces = list(db.faces.find(query))
    
    if not unassigned_faces:
        return stats
    
    # Get all existing persons
    existing_persons = list(db.persons.find())
    
    # Build encoding lookup for existing persons
    person_encodings: Dict[str, List[np.ndarray]] = {}
    for person_doc in existing_persons:
        person_id = str(person_doc["_id"])
        faces = list(db.faces.find({"person_id": person_id}))
        
        encodings = []
        for face in faces:
            if face.get("encoding"):
                encodings.append(bytes_to_encoding(face["encoding"]))
        if encodings:
            person_encodings[person_id] = encodings
    
    # Process each unassigned face
    for face in unassigned_faces:
        if not face.get("encoding"):
            continue
        
        face_encoding = bytes_to_encoding(face["encoding"])
        face_id = str(face["_id"])
        stats["faces_processed"] += 1
        
        # Determine tolerance based on encoding dimension
        # 512-dim = InsightFace (cosine distance), 128-dim = face-api.js (Euclidean)
        tolerance = settings.insightface_tolerance if len(face_encoding) == 512 else settings.face_recognition_tolerance
        
        # Try to find a matching person
        best_match = _find_matching_person(
            face_encoding, 
            person_encodings,
            tolerance
        )
        
        if best_match:
            person_id, distance = best_match
            
            db.faces.update_one(
                {"_id": face["_id"]},
                {"$set": {"person_id": person_id}}
            )
            stats["matched_to_existing"] += 1
            
            if person_id not in person_encodings:
                person_encodings[person_id] = []
            person_encodings[person_id].append(face_encoding)
        else:
            # Create a new person
            new_person_data = {
                "name": None,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "representative_face_id": None,
            }
            result = db.persons.insert_one(new_person_data)
            new_person_id = str(result.inserted_id)
            
            db.faces.update_one(
                {"_id": face["_id"]},
                {"$set": {"person_id": new_person_id}}
            )
            
            db.persons.update_one(
                {"_id": result.inserted_id},
                {"$set": {"representative_face_id": face_id}}
            )
            
            person_encodings[new_person_id] = [face_encoding]
            stats["new_persons_created"] += 1
    
    return stats


def _find_matching_person(
    face_encoding: np.ndarray,
    person_encodings: Dict[str, List[np.ndarray]],
    tolerance: float
) -> Optional[Tuple[str, float]]:
    """
    Find the best matching person for a face encoding.
    
    Automatically detects encoding type:
    - 128-dim (face-api.js): Uses Euclidean distance
    - 512-dim (InsightFace): Uses cosine distance (1 - similarity)
    """
    best_match = None
    best_distance = float('inf')
    
    # Detect encoding type based on dimension
    is_insightface = len(face_encoding) == 512
    
    for person_id, encodings in person_encodings.items():
        if not encodings:
            continue
        
        # Skip if encoding dimensions don't match
        if len(encodings[0]) != len(face_encoding):
            continue
        
        # Calculate distance to each face of this person
        distances = []
        for enc in encodings:
            if is_insightface:
                # Cosine distance for InsightFace (embeddings are normalized)
                similarity = np.dot(face_encoding, enc)
                distance = 1 - similarity
            else:
                # Euclidean distance for face-api.js
                distance = np.linalg.norm(face_encoding - enc)
            distances.append(distance)
        
        # Use minimum distance
        min_distance = min(distances)
        
        if min_distance < tolerance and min_distance < best_distance:
            best_distance = min_distance
            best_match = (person_id, min_distance)
    
    return best_match


async def merge_persons(db: AsyncIOMotorDatabase, source_id: str, target_id: str) -> bool:
    """
    Merge two person clusters.
    """
    source_oid = to_object_id(source_id)
    target_oid = to_object_id(target_id)
    
    if not source_oid or not target_oid:
        return False
    
    source = await db.persons.find_one({"_id": source_oid})
    target = await db.persons.find_one({"_id": target_oid})
    
    if not source or not target:
        return False
    
    if source_id == target_id:
        return False
    
    # Move all faces from source to target
    await db.faces.update_many(
        {"person_id": source_id},
        {"$set": {"person_id": target_id}}
    )
    
    # Delete the source person
    await db.persons.delete_one({"_id": source_oid})
    
    # Update representative face if needed
    await _update_representative_face(db, target_id)
    
    return True


async def _update_representative_face(db: AsyncIOMotorDatabase, person_id: str) -> None:
    """Update the representative face for a person."""
    oid = to_object_id(person_id)
    if not oid:
        return
    
    person = await db.persons.find_one({"_id": oid})
    if not person:
        return
    
    # Get first face
    face = await db.faces.find_one({"person_id": person_id})
    if face:
        await db.persons.update_one(
            {"_id": oid},
            {"$set": {"representative_face_id": str(face["_id"])}}
        )


async def recalculate_all_clusters(db: AsyncIOMotorDatabase) -> Dict[str, int]:
    """
    Recalculate all face clusters from scratch.
    """
    # Remove all person assignments
    await db.faces.update_many({}, {"$set": {"person_id": None}})
    
    # Delete all persons
    await db.persons.delete_many({})
    
    # Get all faces with encodings
    cursor = db.faces.find({"encoding": {"$ne": None}})
    faces = await cursor.to_list(length=100000)
    
    face_ids = [str(f["_id"]) for f in faces]
    
    # Re-cluster
    return await cluster_faces(db, face_ids)


def recalculate_all_clusters_sync(db) -> Dict[str, int]:
    """
    Recalculate all face clusters from scratch (sync version).
    """
    # Remove all person assignments
    db.faces.update_many({}, {"$set": {"person_id": None}})
    
    # Delete all persons
    db.persons.delete_many({})
    
    # Get all faces with encodings
    faces = list(db.faces.find({"encoding": {"$ne": None}}))
    
    face_ids = [str(f["_id"]) for f in faces]
    
    # Re-cluster
    return cluster_faces_sync(db, face_ids)
