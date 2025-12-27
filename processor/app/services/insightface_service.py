"""InsightFace service for fast and accurate face detection/recognition."""
import os

# Optimization: Limit threading for ONNX and libraries to avoid contention between workers
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["ORT_LOGGING_LEVEL"] = "3"

import numpy as np
from typing import List, Tuple, Optional
from PIL import Image
import os

import io
import sys
import contextlib

# Lazy loading of InsightFace
_app = None


@contextlib.contextmanager
def suppress_stdout():
    with open(os.devnull, "w") as devnull:
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = devnull
        sys.stderr = devnull
        try:
            yield
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr


def get_face_analyzer():
    """Get or initialize the InsightFace analyzer (lazy loading)."""
    global _app
    if _app is None:
        with suppress_stdout():
            from insightface.app import FaceAnalysis
            
            # Use buffalo_m model - same accuracy as buffalo_l but faster detection (2.5GF vs 10GF)
            # We pass provider options directly in the providers list for better compatibility
            _app = FaceAnalysis(
                name='buffalo_l',
                providers=[('CPUExecutionProvider', {'intra_op_num_threads': 1})]
            )
            # ctx_id=0 for GPU, -1 for CPU
            # det_size=(640, 640) is a good balance. 
            _app.prepare(ctx_id=-1, det_size=(640, 640))
    return _app


def analyze_image(image_data, min_score=0.65, edge_margin=10):
    """
    Analyze image and return full face objects.
    
    Args:
        image_data: Image data in bytes, PIL Image, or numpy array
        min_score: Minimum detection score to accept a face
        edge_margin: Minimum distance from image edge to accept a face (filters partial faces)
        
    Returns:
        List of InsightFace face objects
    """
    try:
        if isinstance(image_data, bytes):
            img = Image.open(io.BytesIO(image_data))
            if img.mode != 'RGB':
                img = img.convert('RGB')
            img_array = np.array(img)
        elif isinstance(image_data, Image.Image):
            if image_data.mode != 'RGB':
                image_data = image_data.convert('RGB')
            img_array = np.array(image_data)
        elif isinstance(image_data, np.ndarray):
            img_array = image_data
        else:
            raise ValueError("Unsupported image data type")
        
        # Detect faces
        with suppress_stdout():
            app = get_face_analyzer()
            faces = app.get(img_array)
            
        # Filter faces
        filtered_faces = []
        height, width = img_array.shape[:2]
        
        for face in faces:
            # Filter by detection score
            if face.det_score < min_score:
                continue
                
            # Filter partial faces (touching edges)
            bbox = face.bbox.astype(int)
            x1, y1, x2, y2 = bbox
            
            if (x1 < edge_margin or 
                y1 < edge_margin or 
                x2 > width - edge_margin or 
                y2 > height - edge_margin):
                continue
                
            filtered_faces.append(face)
            
        return filtered_faces
    except Exception as e:
        print(f"Error analyzing image: {e}")
        return []


def detect_faces(image_path: str) -> List[Tuple[Tuple[int, int, int, int], np.ndarray]]:
    """
    Detect faces in an image using InsightFace.
    
    Args:
        image_path: Path to the image file
        
    Returns:
        List of tuples: ((top, right, bottom, left), embedding_512d)
    """
    if not os.path.exists(image_path):
        return []
    
    try:
        # Load image
        img = Image.open(image_path)
        if img.mode != 'RGB':
            img = img.convert('RGB')
        img_array = np.array(img)
        
        # Detect faces
        app = get_face_analyzer()
        faces = app.get(img_array)
        
        results = []
        for face in faces:
            # Get bounding box (x1, y1, x2, y2) and convert to (top, right, bottom, left)
            bbox = face.bbox.astype(int)
            x1, y1, x2, y2 = bbox
            top, right, bottom, left = y1, x2, y2, x1
            
            # Get 512-dimensional embedding and normalize it
            embedding = face.embedding
            norm = np.linalg.norm(embedding)
            if norm > 0:
                embedding = embedding / norm  # Normalize for cosine similarity
            
            results.append(((top, right, bottom, left), embedding))
        
        return results
        
    except Exception as e:
        print(f"Error detecting faces in {image_path}: {e}")
        return []


def encoding_to_bytes(encoding: np.ndarray) -> bytes:
    """Convert a face encoding numpy array to bytes for storage."""
    return encoding.astype(np.float32).tobytes()


def bytes_to_encoding(data: bytes) -> np.ndarray:
    """Convert stored bytes back to a face encoding numpy array."""
    return np.frombuffer(data, dtype=np.float32)


def compare_faces(
    known_encoding: np.ndarray,
    face_encoding: np.ndarray,
    threshold: float = 0.4
) -> Tuple[bool, float]:
    """
    Compare two face encodings using cosine similarity.
    
    InsightFace embeddings are already normalized, so cosine similarity
    is just the dot product.
    
    Args:
        known_encoding: Known face encoding (512-dim)
        face_encoding: Face encoding to compare (512-dim)
        threshold: Similarity threshold (0.4 is a good default for ArcFace)
        
    Returns:
        Tuple of (is_match, similarity_score)
    """
    # Cosine similarity (embeddings are already normalized)
    similarity = np.dot(known_encoding, face_encoding)
    
    # Higher similarity = more similar (opposite of distance)
    is_match = similarity > threshold
    
    return is_match, float(similarity)


def face_distance(face_encodings: List[np.ndarray], face_to_compare: np.ndarray) -> np.ndarray:
    """
    Calculate distance between a face encoding and a list of encodings.
    
    For compatibility with existing clustering code, we return 1 - cosine_similarity
    so that lower values mean more similar (like Euclidean distance).
    
    Args:
        face_encodings: List of known face encodings
        face_to_compare: Face encoding to compare
        
    Returns:
        Array of distances (0 = identical, 2 = completely different)
    """
    if len(face_encodings) == 0:
        return np.array([])
    
    # Stack encodings for batch computation
    encodings_array = np.array(face_encodings)
    
    # Cosine similarity (embeddings are normalized)
    similarities = np.dot(encodings_array, face_to_compare)
    
    # Convert to distance (1 - similarity)
    # This makes it compatible with the existing clustering tolerance logic
    distances = 1 - similarities
    
    return distances
