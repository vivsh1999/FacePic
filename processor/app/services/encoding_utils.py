"""Encoding utility functions for face vectors."""
import numpy as np


def encoding_to_bytes(encoding: np.ndarray) -> bytes:
    """Convert numpy encoding array to bytes for storage."""
    return encoding.tobytes()


def bytes_to_encoding(data: bytes) -> np.ndarray:
    """
    Convert bytes back to numpy encoding array.
    
    Auto-detects dtype based on byte length:
    - 512 bytes = 128 float32 values (face-api.js)
    - 1024 bytes = 128 float64 values (legacy face_recognition/dlib)
    - 2048 bytes = 512 float32 values (InsightFace)
    """
    byte_len = len(data)
    
    if byte_len == 2048:
        # InsightFace: 512 dimensions * 4 bytes (float32)
        return np.frombuffer(data, dtype=np.float32)
    elif byte_len == 1024:
        # Legacy dlib/face_recognition: 128 dimensions * 8 bytes (float64)
        return np.frombuffer(data, dtype=np.float64)
    elif byte_len == 512:
        # face-api.js: 128 dimensions * 4 bytes (float32)
        return np.frombuffer(data, dtype=np.float32)
    else:
        # Fallback: try float64
        return np.frombuffer(data, dtype=np.float64)
