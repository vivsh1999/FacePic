import os
import uuid
import json
import mimetypes
import io
import warnings
import numpy as np
from tqdm import tqdm
from datetime import datetime, timezone
from PIL import Image
from bson import ObjectId

# Suppress warnings
warnings.filterwarnings("ignore")
# Suppress ONNX Runtime warnings
os.environ["ORT_LOGGING_LEVEL"] = "3"

from ..config import get_settings
from ..database import get_sync_database
from .storage_service import get_storage_service
from .insightface_service import analyze_image

settings = get_settings()

class BatchProcessor:
    def __init__(self, upload_enabled=True):
        self.db = get_sync_database()
        self.storage = get_storage_service()
        self.import_dir = settings.import_dir
        self.processed_log_file = settings.processed_log_file
        self.upload_enabled = upload_enabled
        self.person_score_cache = {} # Cache for person_id -> best_score

    def get_person_best_score(self, person_id):
        """Get the best face score for a person from cache or DB."""
        if person_id in self.person_score_cache:
            return self.person_score_cache[person_id]
            
        person = self.db.persons.find_one({"_id": ObjectId(person_id)})
        if person and "metadata" in person and "best_face_score" in person["metadata"]:
            score = person["metadata"]["best_face_score"]
            self.person_score_cache[person_id] = score
            return score
        return 0.0

    def update_person_best_score(self, person_id, score):
        """Update the best face score for a person."""
        self.person_score_cache[person_id] = score
        self.db.persons.update_one(
            {"_id": ObjectId(person_id)},
            {"$set": {"metadata.best_face_score": score}}
        )

    def load_processed_log(self):
        log_data = {}
        if os.path.exists(self.processed_log_file):
            try:
                with open(self.processed_log_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if not line: continue
                        try:
                            entry = json.loads(line)
                            # Entry format: {"key": "path/to/file", "data": {...}}
                            if "key" in entry and "data" in entry:
                                log_data[entry["key"]] = entry["data"]
                        except json.JSONDecodeError:
                            continue
            except Exception as e:
                print(f"Error loading log file: {e}")
        return log_data

    def append_to_log(self, key, data):
        # Ensure directory exists
        os.makedirs(os.path.dirname(self.processed_log_file), exist_ok=True)
        entry = {"key": key, "data": data}
        with open(self.processed_log_file, 'a') as f:
            f.write(json.dumps(entry) + "\n")

    def create_thumbnail(self, image_bytes, size=(300, 300)):
        """Create a thumbnail from image bytes."""
        img = Image.open(io.BytesIO(image_bytes))
        img.thumbnail(size)
        thumb_io = io.BytesIO()
        img.save(thumb_io, format=img.format)
        thumb_io.seek(0)
        return thumb_io

    def find_matching_person(self, face_encoding, threshold=0.4):
        """Find a matching person for a face encoding using Cosine Similarity."""
        persons = self.db.persons.find()
        
        best_match_person_id = None
        max_similarity = -1.0

        for person in persons:
            person_id = str(person["_id"])
            # Get faces for this person
            faces = self.db.faces.find({"person_id": person_id})
            
            known_encodings = []
            for face in faces:
                if "encoding" in face:
                    enc_arr = np.array(face["encoding"])
                    if enc_arr.shape == (512,):
                        known_encodings.append(enc_arr)
            
            if not known_encodings:
                continue

            # Calculate cosine similarity
            try:
                known_encodings_arr = np.array(known_encodings)
                if known_encodings_arr.ndim == 1:
                    # Handle case where it might be flattened unexpectedly
                    known_encodings_arr = known_encodings_arr.reshape(1, -1)
                
                similarities = np.dot(known_encodings_arr, face_encoding)
                best_similarity = np.max(similarities)

                if best_similarity > threshold and best_similarity > max_similarity:
                    max_similarity = best_similarity
                    best_match_person_id = person_id
            except Exception as e:
                print(f"Error calculating similarity for person {person_id}: {e}")
                continue

        return best_match_person_id

    def get_or_create_folder(self, relative_path):
        """Ensure folder structure exists in DB and return the ID of the leaf folder."""
        if not relative_path or relative_path == '.':
            return None
            
        parts = relative_path.split(os.sep)
        parent_id = None
        current_path = ""
        
        for part in parts:
            if not part: continue
            
            current_path = f"{current_path}/{part}" if current_path else f"/{part}"
            
            # Try to find existing folder
            folder = self.db.folders.find_one({"path": current_path})
            
            if not folder:
                # Create new folder
                result = self.db.folders.insert_one({
                    "name": part,
                    "parent_id": parent_id,
                    "path": current_path,
                    "created_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc)
                })
                parent_id = result.inserted_id
            else:
                parent_id = folder["_id"]
                
        return str(parent_id)

    def process_image(self, filename, file_path, folder_id=None, relative_path=None):
        # print(f"Processing {filename}...")
        try:
            # 1. Read Image
            with open(file_path, 'rb') as f:
                image_bytes = f.read()
            
            # Basic mime check
            mime_type, _ = mimetypes.guess_type(file_path)
            if not mime_type:
                mime_type = "application/octet-stream"

            # Generate unique ID for storage
            ext = os.path.splitext(filename)[1]
            unique_filename = f"{uuid.uuid4()}{ext}"
            
            # 2. Detect Faces
            faces = analyze_image(image_bytes)
            
            # 3. Upload to R2 (Conditional) or Save Locally
            thumb_filename = f"thumb_{unique_filename}"
            thumb_io = self.create_thumbnail(image_bytes)
            
            # Ensure thumbnail directory exists
            os.makedirs(settings.thumbnail_dir, exist_ok=True)
            local_thumb_path = os.path.join(settings.thumbnail_dir, thumb_filename)
            
            # Always save locally for API access
            with open(local_thumb_path, 'wb') as f:
                f.write(thumb_io.getvalue())
            
            if self.upload_enabled:
                # Upload Original
                self.storage.upload_bytes(image_bytes, unique_filename, mime_type)
                
                # Upload Thumbnail
                thumb_io.seek(0)
                self.storage.upload_fileobj(thumb_io, thumb_filename, mime_type)

            # 4. Create Image Record
            img = Image.open(io.BytesIO(image_bytes))
            width, height = img.size
            
            # Extract EXIF metadata
            metadata = {}
            try:
                exif = img.getexif()
                if exif:
                    if 306 in exif: metadata['DateTime'] = exif[306]
                    if 271 in exif: metadata['Make'] = exif[271]
                    if 272 in exif: metadata['Model'] = exif[272]
                    
                    gps_info = exif.get_ifd(0x8825)
                    if gps_info and 1 in gps_info and 2 in gps_info and 3 in gps_info and 4 in gps_info:
                        def to_deg(dms, ref):
                            d = float(dms[0]) + float(dms[1])/60.0 + float(dms[2])/3600.0
                            return -d if ref in ['S', 'W'] else d
                            
                        metadata['location'] = {
                            'latitude': to_deg(gps_info[2], gps_info[1]),
                            'longitude': to_deg(gps_info[4], gps_info[3])
                        }
            except Exception as e:
                print(f"Metadata warning: {e}")

            image_doc = {
                "filename": unique_filename,
                "original_filename": filename,
                "filepath": unique_filename if self.upload_enabled else None,
                "thumbnail_path": local_thumb_path,
                "width": width,
                "height": height,
                "file_size": len(image_bytes),
                "mime_type": mime_type,
                "uploaded_at": datetime.now(timezone.utc),
                "processed": True,
                "is_uploaded": self.upload_enabled,
                "relative_path": relative_path,
                "processed_at": datetime.now(timezone.utc),
                "metadata": metadata,
                "folder_id": folder_id
            }
            result = self.db.images.insert_one(image_doc)
            image_id = result.inserted_id

            # 5. Process Faces
            # Ensure face thumbnails directory exists
            face_thumb_dir = os.path.join(settings.thumbnail_dir, "faces")
            os.makedirs(face_thumb_dir, exist_ok=True)
            
            faces_info = []

            for face_obj in faces:
                # Get bounding box
                bbox = face_obj.bbox.astype(int)
                x1, y1, x2, y2 = bbox
                top, right, bottom, left = int(y1), int(x2), int(y2), int(x1)
                
                # Get embedding first to find person
                encoding = face_obj.embedding
                
                # Validate encoding shape
                if encoding.shape != (512,):
                    # print(f"Skipping face with invalid encoding shape: {encoding.shape}")
                    continue
                    
                norm = np.linalg.norm(encoding)
                if norm > 0:
                    encoding = encoding / norm
                
                # Find matching person
                person_id = self.find_matching_person(encoding)
                
                if not person_id:
                    # Create new person
                    result = self.db.persons.insert_one({
                        "name": None,
                        "created_at": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc),
                        "metadata": {}
                    })
                    person_id = str(result.inserted_id)
                    # print(f"  Created new person: {person_id}")
                else:
                    pass
                    # print(f"  Matched to person: {person_id}")

                # Check if this is a better face for the person
                current_score = float(face_obj.det_score) if hasattr(face_obj, 'det_score') else 0.0
                best_score = self.get_person_best_score(person_id)
                
                # Use a stable filename for the person's thumbnail
                face_thumb_filename = f"person_{person_id}.jpg"
                local_face_path = os.path.join(face_thumb_dir, face_thumb_filename)
                
                # If this is a better face OR the file doesn't exist yet, save/overwrite it
                if current_score > best_score or not os.path.exists(local_face_path):
                    try:
                        face_img = img.crop((left, top, right, bottom))
                        
                        # Save/Overwrite Face Thumbnail Locally
                        face_img.save(local_face_path, format="JPEG", quality=85)
                        
                        # Upload Face Thumbnail if enabled (overwrite in R2)
                        if self.upload_enabled:
                            face_thumb_io = io.BytesIO()
                            face_img.save(face_thumb_io, format="JPEG", quality=85)
                            face_thumb_io.seek(0)
                            self.storage.upload_fileobj(face_thumb_io, f"faces/{face_thumb_filename}", "image/jpeg")
                            
                        # Update best score
                        self.update_person_best_score(person_id, current_score)
                        # print(f"  Updated best face for {person_id} (score: {current_score:.4f})")
                        
                    except Exception as e:
                        print(f"Error cropping face: {e}")
                        # If failed to create new one, try to fallback to existing if it exists
                        if not os.path.exists(local_face_path):
                            local_face_path = None

                # Extract face metadata
                face_metadata = {
                    "det_score": current_score,
                    "age": int(face_obj.age) if hasattr(face_obj, 'age') else None,
                    "gender": int(face_obj.gender) if hasattr(face_obj, 'gender') else None,
                }

                # Save Face
                face_doc_result = self.db.faces.insert_one({
                    "image_id": image_id,
                    "person_id": person_id,
                    "encoding": encoding.tolist(),
                    "location": {
                        "top": top,
                        "right": right,
                        "bottom": bottom,
                        "left": left
                    },
                    "thumbnail_path": local_face_path,
                    "created_at": datetime.now(timezone.utc),
                    "metadata": face_metadata
                })
                
                faces_info.append({
                    "face_id": str(face_doc_result.inserted_id),
                    "person_id": person_id,
                    "thumbnail_path": local_face_path
                })

            return thumb_filename, faces_info
        except Exception as e:
            print(f"Error processing {filename}: {e}")
            import traceback
            traceback.print_exc()
            return None
        except Exception as e:
            print(f"Error processing {filename}: {e}")
            import traceback
            traceback.print_exc()
            return None

    def run(self):
        """Scan local directory recursively, process images, upload to R2, and update DB."""
        if not os.path.exists(self.import_dir):
            print(f"Import directory {self.import_dir} does not exist.")
            return

        processed_log = self.load_processed_log()
        processed_count = len(processed_log)
        
        if processed_count > 0:
            print(f"Resuming scan... Found {processed_count} previously processed images.")
        
        print("Scanning files...")
        candidates = []
        # Use os.walk to scan recursively
        for root, dirs, files in os.walk(self.import_dir):
            # Calculate relative path for folder structure
            rel_path = os.path.relpath(root, self.import_dir)
            
            # Get or create folder ID (skip for root '.')
            folder_id = None
            if rel_path != '.':
                folder_id = self.get_or_create_folder(rel_path)
            
            for filename in files:
                # Use relative path + filename as key for processed log to avoid collisions
                # e.g. "Vacation/photo.jpg" instead of just "photo.jpg"
                log_key = os.path.join(rel_path, filename)
                if rel_path == '.':
                    log_key = filename
                    
                if log_key in processed_log:
                    continue

                file_path = os.path.join(root, filename)
                
                if filename.startswith('.'):
                    continue
                    
                mime_type, _ = mimetypes.guess_type(file_path)
                if not mime_type or not mime_type.startswith('image/'):
                    # print(f"Skipping non-image: {filename}")
                    continue
                
                candidates.append((filename, file_path, folder_id, log_key))

        print(f"Found {len(candidates)} new images to process (skipped {processed_count} already processed).")
        if not candidates:
            return

        count = 0
        for filename, file_path, folder_id, log_key in tqdm(candidates, desc="Processing Images", unit="img"):
            result = self.process_image(filename, file_path, folder_id, relative_path=log_key)
            if result:
                thumb_filename, faces_info = result
                log_entry = {
                    "processed_at": datetime.now(timezone.utc).isoformat(),
                    "thumbnail": thumb_filename,
                    "faces": faces_info
                }
                # Update in-memory log (optional, but good for consistency if we loop again)
                processed_log[log_key] = log_entry
                # Append to disk log
                self.append_to_log(log_key, log_entry)
                count += 1
                # print(f"Done: {log_key}")

        print(f"Processed {count} new images.")

    def process_pending_uploads(self):
        """Scan DB for images that are processed but not uploaded, and upload them."""
        print("Scanning for pending uploads...")
        query = {"is_uploaded": False}
        total_pending = self.db.images.count_documents(query)
        
        if total_pending == 0:
            print("No pending uploads found.")
            return

        print(f"Found {total_pending} images pending upload.")
        pending_images = self.db.images.find(query)
        count = 0
        
        for image in tqdm(pending_images, total=total_pending, desc="Uploading", unit="img"):
            relative_path = image.get("relative_path")
            if not relative_path:
                # print(f"Skipping image {image['_id']}: No relative path found.")
                continue
                
            file_path = os.path.join(self.import_dir, relative_path)
            if not os.path.exists(file_path):
                # print(f"Skipping image {image['_id']}: File not found at {file_path}")
                continue
                
            # print(f"Uploading pending image: {relative_path}")
            try:
                with open(file_path, 'rb') as f:
                    image_bytes = f.read()
                
                unique_filename = image["filename"] # Reuse the generated filename
                mime_type = image.get("mime_type", "application/octet-stream")
                
                # Upload Original
                self.storage.upload_bytes(image_bytes, unique_filename, mime_type)
                
                # Upload Thumbnail
                thumb_filename = image.get("thumbnail_path")
                if not thumb_filename:
                    thumb_filename = f"thumb_{unique_filename}"
                
                # Try to find local thumbnail first
                local_thumb_path = os.path.join(settings.thumbnail_dir, thumb_filename)
                if os.path.exists(local_thumb_path):
                    with open(local_thumb_path, 'rb') as f:
                        self.storage.upload_fileobj(f, thumb_filename, mime_type)
                else:
                    # Regenerate if missing
                    thumb_io = self.create_thumbnail(image_bytes)
                    self.storage.upload_fileobj(thumb_io, thumb_filename, mime_type)
                
                # Update DB
                self.db.images.update_one(
                    {"_id": image["_id"]},
                    {
                        "$set": {
                            "is_uploaded": True,
                            "filepath": unique_filename,
                            "thumbnail_path": thumb_filename
                        }
                    }
                )
                count += 1
                # print(f"Uploaded: {relative_path}")
                
            except Exception as e:
                print(f"Error uploading {relative_path}: {e}")
                
        print(f"Uploaded {count} pending images.")

def run_batch_processor(upload_enabled=True, upload_only=False):
    processor = BatchProcessor(upload_enabled=upload_enabled)
    if upload_only:
        processor.process_pending_uploads()
    else:
        processor.run()
