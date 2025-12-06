"""Face detection and recognition service."""
import numpy as np
from typing import List, Tuple, Optional
import face_recognition
from PIL import Image as PILImage

from ..config import get_settings
from .image_service import create_face_thumbnail

settings = get_settings()


def detect_faces(image_path: str) -> List[Tuple[Tuple[int, int, int, int], np.ndarray]]:
    """
    Detect faces in an image and compute their encodings.
    
    Args:
        image_path: Path to the image file
    
    Returns:
        List of tuples containing (bounding_box, encoding)
        bounding_box is (top, right, bottom, left)
        encoding is a 128-dimensional numpy array
    """
    # Load image
    image = face_recognition.load_image_file(image_path)
    
    # Detect face locations
    # model can be 'hog' (faster, less accurate) or 'cnn' (slower, more accurate)
    face_locations = face_recognition.face_locations(
        image, 
        model=settings.face_recognition_model
    )
    
    if not face_locations:
        return []
    
    # Compute face encodings for each detected face
    face_encodings = face_recognition.face_encodings(image, face_locations)
    
    # Combine locations with encodings
    results = []
    for location, encoding in zip(face_locations, face_encodings):
        results.append((location, encoding))
    
    return results


def encoding_to_bytes(encoding: np.ndarray) -> bytes:
    """Convert numpy encoding array to bytes for storage."""
    return encoding.tobytes()


def bytes_to_encoding(data: bytes) -> np.ndarray:
    """Convert bytes back to numpy encoding array."""
    return np.frombuffer(data, dtype=np.float64)


def compare_faces(
    known_encodings: List[np.ndarray],
    face_encoding: np.ndarray,
    tolerance: Optional[float] = None
) -> Tuple[List[bool], List[float]]:
    """
    Compare a face encoding against a list of known encodings.
    
    Args:
        known_encodings: List of known face encodings
        face_encoding: The face encoding to compare
        tolerance: Distance threshold for match (lower = stricter)
    
    Returns:
        Tuple of (matches, distances)
        matches: List of boolean values indicating if each known face matches
        distances: List of distances to each known face
    """
    if tolerance is None:
        tolerance = settings.face_recognition_tolerance
    
    if not known_encodings:
        return [], []
    
    # Calculate distances
    distances = face_recognition.face_distance(known_encodings, face_encoding)
    
    # Determine matches based on tolerance
    matches = list(distances <= tolerance)
    
    return matches, list(distances)


def find_best_match(
    known_encodings: List[np.ndarray],
    known_person_ids: List[str],
    face_encoding: np.ndarray,
    tolerance: Optional[float] = None
) -> Optional[Tuple[str, float]]:
    """
    Find the best matching person for a face encoding.
    
    Args:
        known_encodings: List of known face encodings
        known_person_ids: List of person IDs corresponding to encodings
        face_encoding: The face encoding to match
        tolerance: Distance threshold for match
    
    Returns:
        Tuple of (person_id, distance) for best match, or None if no match
    """
    if tolerance is None:
        tolerance = settings.face_recognition_tolerance
    
    if not known_encodings:
        return None
    
    matches, distances = compare_faces(known_encodings, face_encoding, tolerance)
    
    if not any(matches):
        return None
    
    # Find the best (smallest distance) match
    best_idx = np.argmin(distances)
    
    if distances[best_idx] <= tolerance:
        return known_person_ids[best_idx], distances[best_idx]
    
    return None


def get_face_quality_score(image_path: str, bbox: Tuple[int, int, int, int]) -> float:
    """
    Calculate a quality score for a face crop.
    Higher scores indicate better quality (larger, more centered faces).
    
    Args:
        image_path: Path to the image
        bbox: Bounding box (top, right, bottom, left)
    
    Returns:
        Quality score between 0 and 1
    """
    top, right, bottom, left = bbox
    face_width = right - left
    face_height = bottom - top
    face_area = face_width * face_height
    
    # Load image to get dimensions
    with PILImage.open(image_path) as img:
        img_area = img.width * img.height
    
    # Score based on face size relative to image
    # Larger faces relative to image = better quality
    size_score = min(1.0, (face_area / img_area) * 10)
    
    # Score based on aspect ratio (prefer square-ish faces)
    aspect_ratio = face_width / face_height if face_height > 0 else 0
    aspect_score = 1.0 - abs(1.0 - aspect_ratio) * 0.5
    aspect_score = max(0, min(1, aspect_score))
    
    # Combined score
    return (size_score * 0.7) + (aspect_score * 0.3)
