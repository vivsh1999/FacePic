"""Application configuration settings."""
import os
from pathlib import Path
from pydantic_settings import BaseSettings
from functools import lru_cache

# Get the backend directory path
BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # MongoDB
    mongodb_url: str = "mongodb://localhost:27017"
    mongodb_database: str = "facepic"
    
    # Storage paths
    upload_dir: str = "./uploads"
    thumbnail_dir: str = "./thumbnails"
    import_dir: str = "/app/import_images"
    processed_log_file: str = "/app/uploads/processed_log.jsonl"

    # R2 Storage
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket_name: str = "facepic"
    
    # Face recognition settings
    face_recognition_tolerance: float = 0.6  # For 128-dim face-api.js embeddings
    face_recognition_model: str = "hog"  # 'hog' or 'cnn'
    
    # InsightFace settings (512-dim ArcFace embeddings)
    insightface_tolerance: float = 0.4  # Cosine distance threshold (1 - similarity)
    use_insightface: bool = True  # Use InsightFace for server-side detection
    
    # Server settings
    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    
    class Config:
        env_file = str(BACKEND_DIR / ".env")
        env_file_encoding = "utf-8"
    
    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in self.cors_origins.split(",")]
    
    def setup_directories(self) -> None:
        """Create necessary directories if they don't exist."""
        dirs = [
            self.upload_dir,
            self.thumbnail_dir,
            f"{self.thumbnail_dir}/images",
            f"{self.thumbnail_dir}/faces",
        ]
        for dir_path in dirs:
            Path(dir_path).mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    settings = Settings()
    settings.setup_directories()
    return settings
