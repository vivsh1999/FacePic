"""Application configuration settings."""
import os
from pathlib import Path
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database
    database_url: str = "sqlite:///./imagetag.db"
    
    # Storage paths
    upload_dir: str = "./uploads"
    thumbnail_dir: str = "./thumbnails"
    
    # Face recognition settings
    face_recognition_tolerance: float = 0.6
    face_recognition_model: str = "hog"  # 'hog' or 'cnn'
    
    # Server settings
    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    
    class Config:
        env_file = ".env"
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
