"""Storage service for R2/S3 interactions."""
import boto3
import io
from typing import Optional, BinaryIO
from ..config import get_settings

settings = get_settings()

class StorageService:
    def __init__(self):
        self.s3 = boto3.client('s3',
            endpoint_url=f'https://{settings.r2_account_id}.r2.cloudflarestorage.com',
            aws_access_key_id=settings.r2_access_key_id,
            aws_secret_access_key=settings.r2_secret_access_key
        )
        self.bucket_name = settings.r2_bucket_name

    def upload_fileobj(self, file_obj: BinaryIO, filename: str, content_type: str) -> bool:
        """Upload a file object to R2."""
        try:
            self.s3.upload_fileobj(
                file_obj, 
                self.bucket_name, 
                filename,
                ExtraArgs={'ContentType': content_type}
            )
            return True
        except Exception as e:
            print(f"Error uploading to R2: {e}")
            return False

    def upload_bytes(self, data: bytes, filename: str, content_type: str) -> bool:
        """Upload bytes to R2."""
        file_obj = io.BytesIO(data)
        return self.upload_fileobj(file_obj, filename, content_type)

_storage_service = None

def get_storage_service() -> StorageService:
    global _storage_service
    if _storage_service is None:
        _storage_service = StorageService()
    return _storage_service
