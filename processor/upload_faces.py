import os
import sys
import io
from tqdm import tqdm
from app.database import get_sync_database
from app.services.storage_service import get_storage_service
from app.config import get_settings

# Add the current directory to python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

settings = get_settings()

def upload_faces():
    db = get_sync_database()
    storage = get_storage_service()
    
    print("Scanning for faces...")
    # We don't have an 'is_uploaded' flag for faces, so we check all or check if they exist in R2?
    # Checking R2 for every face is slow.
    # We can assume that if we are running this, we want to ensure all faces are uploaded.
    # Or we can check if the thumbnail_path is absolute (local) and assume it needs upload?
    # But even if uploaded, we might keep absolute path in DB (as seen with images).
    
    # Let's just try to upload all faces that exist locally.
    # R2 overwrite is cheap/free for Class A operations usually? No, Class A is expensive.
    # But we want to avoid re-uploading if possible.
    
    # For now, let's just upload all faces found in the local faces directory.
    
    faces_dir = os.path.join(settings.thumbnail_dir, "faces")
    if not os.path.exists(faces_dir):
        print(f"Faces directory {faces_dir} does not exist.")
        return

    files = [f for f in os.listdir(faces_dir) if f.endswith('.jpg')]
    print(f"Found {len(files)} face thumbnails locally.")
    
    count = 0
    errors = 0
    
    for filename in tqdm(files, desc="Uploading Faces", unit="face"):
        file_path = os.path.join(faces_dir, filename)
        
        try:
            # Key in R2: faces/filename
            key = f"faces/{filename}"
            
            with open(file_path, 'rb') as f:
                storage.upload_fileobj(f, key, "image/jpeg")
            count += 1
        except Exception as e:
            print(f"Error uploading {filename}: {e}")
            errors += 1
            
    print(f"Uploaded {count} faces. Errors: {errors}")

if __name__ == "__main__":
    upload_faces()
