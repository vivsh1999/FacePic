"""Face clustering service for grouping similar faces."""
import numpy as np
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..models import Face, Person
from ..config import get_settings
from .face_service import bytes_to_encoding, find_best_match

settings = get_settings()


def cluster_faces(db: Session, face_ids: Optional[List[int]] = None) -> Dict[str, int]:
    """
    Cluster faces into person groups.
    
    This function takes unassigned faces and either:
    1. Matches them to existing persons
    2. Creates new person clusters for unmatched faces
    
    Args:
        db: Database session
        face_ids: Optional list of specific face IDs to cluster
    
    Returns:
        Dict with counts of matches and new persons created
    """
    stats = {
        "matched_to_existing": 0,
        "new_persons_created": 0,
        "faces_processed": 0,
    }
    
    # Get faces to process
    query = db.query(Face).filter(Face.person_id.is_(None))
    if face_ids:
        query = query.filter(Face.id.in_(face_ids))
    
    unassigned_faces = query.all()
    
    if not unassigned_faces:
        return stats
    
    # Get all existing persons with their face encodings
    existing_persons = db.query(Person).all()
    
    # Build encoding lookup for existing persons
    person_encodings: Dict[int, List[np.ndarray]] = {}
    for person in existing_persons:
        encodings = []
        for face in person.faces:
            if face.encoding:
                encodings.append(bytes_to_encoding(face.encoding))
        if encodings:
            person_encodings[person.id] = encodings
    
    # Process each unassigned face
    for face in unassigned_faces:
        if not face.encoding:
            continue
        
        face_encoding = bytes_to_encoding(face.encoding)
        stats["faces_processed"] += 1
        
        # Try to find a matching person
        best_match = _find_matching_person(
            face_encoding, 
            person_encodings,
            settings.face_recognition_tolerance
        )
        
        if best_match:
            person_id, distance = best_match
            face.person_id = person_id
            stats["matched_to_existing"] += 1
            
            # Add this encoding to the person's encodings for future matching
            if person_id not in person_encodings:
                person_encodings[person_id] = []
            person_encodings[person_id].append(face_encoding)
        else:
            # Create a new person for this face
            new_person = Person()
            db.add(new_person)
            db.flush()  # Get the ID
            
            face.person_id = new_person.id
            new_person.representative_face_id = face.id
            
            # Add to our tracking dict
            person_encodings[new_person.id] = [face_encoding]
            
            stats["new_persons_created"] += 1
    
    db.commit()
    return stats


def _find_matching_person(
    face_encoding: np.ndarray,
    person_encodings: Dict[int, List[np.ndarray]],
    tolerance: float
) -> Optional[Tuple[int, float]]:
    """
    Find the best matching person for a face encoding.
    
    Uses average distance to all faces of a person for more robust matching.
    """
    best_match = None
    best_avg_distance = float('inf')
    
    for person_id, encodings in person_encodings.items():
        if not encodings:
            continue
        
        # Calculate distance to each face of this person
        distances = []
        for enc in encodings:
            distance = np.linalg.norm(face_encoding - enc)
            distances.append(distance)
        
        # Use minimum distance (best match to any face of this person)
        min_distance = min(distances)
        
        if min_distance < tolerance and min_distance < best_avg_distance:
            best_avg_distance = min_distance
            best_match = (person_id, min_distance)
    
    return best_match


def merge_persons(db: Session, source_id: int, target_id: int) -> bool:
    """
    Merge two person clusters.
    
    All faces from source_person are moved to target_person,
    then source_person is deleted.
    
    Args:
        db: Database session
        source_id: Person to merge from (will be deleted)
        target_id: Person to merge into (will be kept)
    
    Returns:
        True if successful, False if persons not found
    """
    source = db.query(Person).filter(Person.id == source_id).first()
    target = db.query(Person).filter(Person.id == target_id).first()
    
    if not source or not target:
        return False
    
    if source_id == target_id:
        return False
    
    # Move all faces from source to target
    for face in source.faces:
        face.person_id = target_id
    
    # Delete the source person
    db.delete(source)
    db.commit()
    
    # Update representative face if needed
    _update_representative_face(db, target_id)
    
    return True


def _update_representative_face(db: Session, person_id: int) -> None:
    """Update the representative face for a person (best quality face)."""
    from .face_service import get_face_quality_score
    
    person = db.query(Person).filter(Person.id == person_id).first()
    if not person or not person.faces:
        return
    
    # For now, just use the first face
    # TODO: Implement quality scoring to pick the best face
    person.representative_face_id = person.faces[0].id
    db.commit()


def recalculate_all_clusters(db: Session) -> Dict[str, int]:
    """
    Recalculate all face clusters from scratch.
    
    This removes all person assignments and re-clusters all faces.
    Useful if tolerance settings have changed.
    
    Returns:
        Stats about the clustering operation
    """
    # Remove all person assignments
    db.query(Face).update({Face.person_id: None})
    
    # Delete all persons
    db.query(Person).delete()
    db.commit()
    
    # Get all faces with encodings
    faces_with_encodings = db.query(Face).filter(Face.encoding.isnot(None)).all()
    
    # Re-cluster
    return cluster_faces(db, [f.id for f in faces_with_encodings])
