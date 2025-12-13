"""Image processing service."""
import os
import uuid
import shutil
import hashlib
from pathlib import Path
from typing import Optional, Tuple
from PIL import Image as PILImage
from fastapi import UploadFile

from ..config import get_settings

settings = get_settings()

# Supported image formats
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}
THUMBNAIL_SIZE = (300, 300)
FACE_THUMBNAIL_SIZE = (150, 150)


def is_valid_image(filename: str) -> bool:
    """Check if file has a valid image extension."""
    ext = Path(filename).suffix.lower()
    return ext in ALLOWED_EXTENSIONS


def generate_unique_filename(original_filename: str) -> str:
    """Generate a unique filename while preserving extension."""
    ext = Path(original_filename).suffix.lower()
    unique_name = f"{uuid.uuid4().hex}{ext}"
    return unique_name


async def save_upload_file(upload_file: UploadFile) -> Tuple[str, str, int]:
    """
    Save an uploaded file to disk.
    
    Returns:
        Tuple of (saved_filepath, unique_filename, file_size)
    """
    unique_filename = generate_unique_filename(upload_file.filename)
    filepath = os.path.join(settings.upload_dir, unique_filename)
    
    # Save the file
    with open(filepath, "wb") as buffer:
        content = await upload_file.read()
        buffer.write(content)
        file_size = len(content)
    
    return filepath, unique_filename, file_size


def get_image_dimensions(filepath: str) -> Tuple[int, int]:
    """Get image width and height."""
    with PILImage.open(filepath) as img:
        return img.size


def get_mime_type(filepath: str) -> str:
    """Get MIME type based on image format."""
    ext = Path(filepath).suffix.lower()
    mime_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".bmp": "image/bmp",
        ".webp": "image/webp",
    }
    return mime_types.get(ext, "application/octet-stream")


def create_thumbnail(
    source_path: str,
    output_dir: str,
    size: Tuple[int, int] = THUMBNAIL_SIZE,
    filename: Optional[str] = None
) -> str:
    """
    Create a thumbnail for an image.
    
    Args:
        source_path: Path to the source image
        output_dir: Directory to save thumbnail
        size: Thumbnail dimensions (width, height)
        filename: Optional custom filename
    
    Returns:
        Path to the created thumbnail
    """
    if filename is None:
        filename = f"thumb_{Path(source_path).name}"
    
    output_path = os.path.join(output_dir, filename)
    
    with PILImage.open(source_path) as img:
        # Convert to RGB if necessary (for PNG with transparency)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        
        # Create thumbnail maintaining aspect ratio
        img.thumbnail(size, PILImage.Resampling.LANCZOS)
        img.save(output_path, "JPEG", quality=85)
    
    return output_path


def create_image_thumbnail(source_path: str, filename: str) -> str:
    """Create thumbnail for an uploaded image."""
    output_dir = f"{settings.thumbnail_dir}/images"
    return create_thumbnail(source_path, output_dir, THUMBNAIL_SIZE, f"thumb_{filename}")


def create_face_thumbnail(
    source_path: str,
    bbox: dict,
    face_id: str,
    padding: float = 0.3
) -> str:
    """
    Create a thumbnail for a detected face.
    
    Args:
        source_path: Path to the source image
        bbox: Bounding box dict with top, right, bottom, left
        face_id: Face ID for filename
        padding: Extra padding around face (percentage)
    
    Returns:
        Path to the created face thumbnail
    """
    output_dir = f"{settings.thumbnail_dir}/faces"
    filename = f"face_{face_id}.jpg"
    output_path = os.path.join(output_dir, filename)
    
    with PILImage.open(source_path) as img:
        # Calculate padded bounding box
        width = bbox["right"] - bbox["left"]
        height = bbox["bottom"] - bbox["top"]
        
        pad_x = int(width * padding)
        pad_y = int(height * padding)
        
        left = max(0, bbox["left"] - pad_x)
        top = max(0, bbox["top"] - pad_y)
        right = min(img.width, bbox["right"] + pad_x)
        bottom = min(img.height, bbox["bottom"] + pad_y)
        
        # Crop the face region
        face_img = img.crop((left, top, right, bottom))
        
        # Convert to RGB if necessary
        if face_img.mode in ("RGBA", "P"):
            face_img = face_img.convert("RGB")
        
        # Resize to thumbnail size
        face_img.thumbnail(FACE_THUMBNAIL_SIZE, PILImage.Resampling.LANCZOS)
        face_img.save(output_path, "JPEG", quality=90)
    
    return output_path


def delete_image_files(filepath: str, thumbnail_path: Optional[str] = None) -> None:
    """Delete image file and its thumbnail."""
    if os.path.exists(filepath):
        os.remove(filepath)
    
    if thumbnail_path and os.path.exists(thumbnail_path):
        os.remove(thumbnail_path)


def delete_face_thumbnail(thumbnail_path: str) -> None:
    """Delete a face thumbnail."""
    if thumbnail_path and os.path.exists(thumbnail_path):
        os.remove(thumbnail_path)


def calculate_file_hash(filepath: str, chunk_size: int = 8192) -> str:
    """
    Calculate MD5 hash of a file for duplicate detection.
    
    Args:
        filepath: Path to the file
        chunk_size: Size of chunks to read
    
    Returns:
        MD5 hash string
    """
    md5_hash = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            md5_hash.update(chunk)
    return md5_hash.hexdigest()


def calculate_image_hash(filepath: str) -> str:
    """
    Calculate a perceptual hash of an image for near-duplicate detection.
    Uses a simple average hash (aHash) algorithm.
    
    Args:
        filepath: Path to the image file
    
    Returns:
        Hex string of the image hash
    """
    with PILImage.open(filepath) as img:
        # Convert to grayscale and resize to 8x8
        img = img.convert("L").resize((8, 8), PILImage.Resampling.LANCZOS)
        pixels = list(img.getdata())
        
        # Calculate average pixel value
        avg = sum(pixels) / len(pixels)
        
        # Create hash based on whether each pixel is above or below average
        bits = "".join("1" if pixel >= avg else "0" for pixel in pixels)
        
        # Convert binary string to hex
        return hex(int(bits, 2))[2:].zfill(16)

