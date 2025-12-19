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
import multiprocessing
import time
import queue
import psutil
import signal

# Suppress warnings
warnings.filterwarnings("ignore")
# Suppress ONNX Runtime warnings
os.environ["ORT_LOGGING_LEVEL"] = "3"

from ..config import get_settings
from ..database import get_sync_database
from .storage_service import get_storage_service
from .insightface_service import analyze_image

settings = get_settings()

# Global variables for worker processes
WORKER_INITIAL_FACES = None
WORKER_NEW_FACES = None

# Cache for optimized matching
_CACHED_INITIAL_MATRIX = None
_CACHED_INITIAL_IDS = None
_CACHED_NEW_MATRIX = None
_CACHED_NEW_IDS = None
_LAST_NEW_FACES_LEN = 0

def init_worker(initial_faces, new_faces_list):
    """Initialize worker process with shared data."""
    global WORKER_INITIAL_FACES, WORKER_NEW_FACES, _CACHED_INITIAL_MATRIX, _CACHED_INITIAL_IDS
    WORKER_INITIAL_FACES = initial_faces
    WORKER_NEW_FACES = new_faces_list
    
    # Pre-build initial matrix
    if WORKER_INITIAL_FACES:
        ids = []
        encs = []
        for pid, enc in WORKER_INITIAL_FACES:
            ids.append(pid)
            encs.append(enc)
        _CACHED_INITIAL_IDS = ids
        _CACHED_INITIAL_MATRIX = np.array(encs)

def create_thumbnail(img, size=(300, 300)):
    """Create a thumbnail from a PIL Image."""
    # Create a copy to avoid modifying the original
    thumb = img.copy()
    thumb.thumbnail(size)
    thumb_io = io.BytesIO()
    # Use JPEG for thumbnails to save space/time
    thumb.save(thumb_io, format="JPEG", quality=85)
    thumb_io.seek(0)
    return thumb_io

def get_person_best_score_from_db(db, person_id):
    """Get the best face score for a person from DB."""
    person = db.persons.find_one({"_id": ObjectId(person_id)})
    if person and "metadata" in person and "best_face_score" in person["metadata"]:
        return person["metadata"]["best_face_score"]
    return 0.0

def update_person_best_score_in_db(db, person_id, score):
    """Update the best face score for a person."""
    db.persons.update_one(
        {"_id": ObjectId(person_id)},
        {"$set": {"metadata.best_face_score": score}}
    )

def find_matching_person_optimized(face_encoding, threshold=0.45):
    """Find a matching person using cached faces (initial + new)."""
    global WORKER_INITIAL_FACES, WORKER_NEW_FACES
    global _CACHED_INITIAL_MATRIX, _CACHED_INITIAL_IDS
    global _CACHED_NEW_MATRIX, _CACHED_NEW_IDS, _LAST_NEW_FACES_LEN
    
    best_similarity = -1.0
    best_person_id = None

    # 1. Check initial faces (static)
    if _CACHED_INITIAL_MATRIX is not None:
        similarities = np.dot(_CACHED_INITIAL_MATRIX, face_encoding)
        idx = np.argmax(similarities)
        if similarities[idx] > best_similarity:
            best_similarity = similarities[idx]
            best_person_id = _CACHED_INITIAL_IDS[idx]

    # 2. Check new faces (dynamic)
    if WORKER_NEW_FACES is not None:
        try:
            current_len = len(WORKER_NEW_FACES)
            if current_len > 0:
                # Update cache if length changed
                if current_len != _LAST_NEW_FACES_LEN:
                    new_faces_snapshot = list(WORKER_NEW_FACES)
                    ids = []
                    encs = []
                    for pid, enc in new_faces_snapshot:
                        ids.append(pid)
                        encs.append(enc)
                    _CACHED_NEW_IDS = ids
                    _CACHED_NEW_MATRIX = np.array(encs)
                    _LAST_NEW_FACES_LEN = current_len
                
                if _CACHED_NEW_MATRIX is not None:
                    similarities = np.dot(_CACHED_NEW_MATRIX, face_encoding)
                    idx = np.argmax(similarities)
                    if similarities[idx] > best_similarity:
                        best_similarity = similarities[idx]
                        best_person_id = _CACHED_NEW_IDS[idx]
        except Exception:
            # Fallback if manager list is being modified
            pass
    
    if best_similarity > threshold:
        return best_person_id
        
    return None

def process_image_task(filename, file_path, folder_id, relative_path, upload_enabled):
    try:
        db = get_sync_database()
        storage = get_storage_service()
        
        with open(file_path, 'rb') as f:
            image_bytes = f.read()
        
        # Open image once
        img = Image.open(io.BytesIO(image_bytes))
        width, height = img.size
        
        # Convert to RGB for InsightFace
        if img.mode != 'RGB':
            img_rgb = img.convert('RGB')
        else:
            img_rgb = img

        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
            mime_type = "application/octet-stream"

        ext = os.path.splitext(filename)[1]
        unique_filename = f"{uuid.uuid4()}{ext}"
        
        # Detect faces using the already opened image
        faces = analyze_image(img_rgb)
        
        thumb_filename = f"thumb_{unique_filename}"
        thumb_io = create_thumbnail(img)
        
        os.makedirs(settings.thumbnail_dir, exist_ok=True)
        local_thumb_path = os.path.join(settings.thumbnail_dir, thumb_filename)
        
        with open(local_thumb_path, 'wb') as f:
            f.write(thumb_io.getvalue())
        
        if upload_enabled:
            storage.upload_bytes(image_bytes, unique_filename, mime_type)
            thumb_io.seek(0)
            storage.upload_fileobj(thumb_io, thumb_filename, "image/jpeg")

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
            pass

        image_doc = {
            "filename": unique_filename,
            "original_filename": filename,
            "filepath": unique_filename if upload_enabled else None,
            "thumbnail_path": local_thumb_path,
            "width": width,
            "height": height,
            "file_size": len(image_bytes),
            "mime_type": mime_type,
            "uploaded_at": datetime.now(timezone.utc),
            "processed": True,
            "is_uploaded": upload_enabled,
            "relative_path": relative_path,
            "processed_at": datetime.now(timezone.utc),
            "metadata": metadata,
            "folder_id": folder_id
        }
        result = db.images.insert_one(image_doc)
        image_id = result.inserted_id

        face_thumb_dir = os.path.join(settings.thumbnail_dir, "faces")
        os.makedirs(face_thumb_dir, exist_ok=True)
        
        faces_info = []
        face_ids = []

        for face_obj in faces:
            bbox = face_obj.bbox.astype(int)
            x1, y1, x2, y2 = bbox
            top, right, bottom, left = int(y1), int(x2), int(y2), int(x1)
            
            encoding = face_obj.embedding
            if encoding.shape != (512,):
                continue
                
            norm = np.linalg.norm(encoding)
            if norm > 0:
                encoding = encoding / norm
            
            person_id = find_matching_person_optimized(encoding)
            
            if not person_id:
                result = db.persons.insert_one({
                    "name": None,
                    "created_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                    "metadata": {}
                })
                person_id = str(result.inserted_id)
                
                if WORKER_NEW_FACES is not None:
                    WORKER_NEW_FACES.append((person_id, encoding))

            current_score = float(face_obj.det_score) if hasattr(face_obj, 'det_score') else 0.0
            best_score = get_person_best_score_from_db(db, person_id)
            
            face_thumb_filename = f"person_{person_id}.jpg"
            local_face_path = os.path.join(face_thumb_dir, face_thumb_filename)
            
            if current_score > best_score or not os.path.exists(local_face_path):
                try:
                    face_img = img.crop((left, top, right, bottom))
                    face_img.save(local_face_path, format="JPEG", quality=85)
                    
                    if upload_enabled:
                        face_thumb_io = io.BytesIO()
                        face_img.save(face_thumb_io, format="JPEG", quality=85)
                        face_thumb_io.seek(0)
                        storage.upload_fileobj(face_thumb_io, f"faces/{face_thumb_filename}", "image/jpeg")
                        
                    update_person_best_score_in_db(db, person_id, current_score)
                except Exception as e:
                    if not os.path.exists(local_face_path):
                        local_face_path = None

            face_metadata = {
                "det_score": current_score,
                "age": int(face_obj.age) if hasattr(face_obj, 'age') else None,
                "gender": int(face_obj.gender) if hasattr(face_obj, 'gender') else None,
            }

            face_doc_result = db.faces.insert_one({
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
            
            face_id = face_doc_result.inserted_id
            face_ids.append(face_id)
            
            faces_info.append({
                "face_id": str(face_id),
                "person_id": person_id,
                "thumbnail_path": local_face_path
            })

        # Update image with faces
        db.images.update_one(
            {"_id": image_id},
            {"$set": {"faces": face_ids}}
        )

        return relative_path, thumb_filename, faces_info
    except Exception as e:
        print(f"Error processing {filename}: {e}")
        import traceback
        traceback.print_exc()
        return None

def worker_loop(task_queue, result_queue, initial_faces, new_faces_list, upload_enabled):
    """Worker process loop."""
    # Ignore SIGINT in workers so the main process can handle cleanup
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    
    init_worker(initial_faces, new_faces_list)
    
    while True:
        try:
            # Timeout allows checking for exit signals or updates
            task = task_queue.get(timeout=1.0)
            if task is None:
                # Sentinel to exit
                break
                
            filename, file_path, folder_id, log_key = task
            result = process_image_task(filename, file_path, folder_id, log_key, upload_enabled)
            
            # Send result back
            result_queue.put((log_key, result))
            
        except queue.Empty:
            continue
        except Exception as e:
            print(f"Worker error: {e}")
            # Ensure we don't hang the main process waiting for a result
            pass

class BatchProcessor:
    def __init__(self, upload_enabled=True):
        self.db = get_sync_database()
        self.storage = get_storage_service()
        self.import_dir = settings.import_dir
        self.processed_log_file = settings.processed_log_file
        self.upload_enabled = upload_enabled

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
                            if "key" in entry and "data" in entry:
                                log_data[entry["key"]] = entry["data"]
                        except json.JSONDecodeError:
                            continue
            except Exception as e:
                print(f"Error loading log file: {e}")
        return log_data

    def append_to_log(self, key, data):
        os.makedirs(os.path.dirname(self.processed_log_file), exist_ok=True)
        entry = {"key": key, "data": data}
        with open(self.processed_log_file, 'a') as f:
            f.write(json.dumps(entry) + "\n")

    def get_or_create_folder(self, relative_path):
        if not relative_path or relative_path == '.':
            return None
            
        parts = relative_path.split(os.sep)
        parent_id = None
        current_path = ""
        
        for part in parts:
            if not part: continue
            
            current_path = f"{current_path}/{part}" if current_path else f"/{part}"
            
            folder = self.db.folders.find_one({"path": current_path})
            
            if not folder:
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

    def get_all_known_faces(self):
        print("Loading known faces from database...")
        all_faces = list(self.db.faces.find(
            {"encoding": {"$exists": True}},
            {"person_id": 1, "encoding": 1}
        ))
        
        known_faces = []
        for face in all_faces:
            if "encoding" in face and "person_id" in face:
                enc_arr = np.array(face["encoding"])
                if enc_arr.shape == (512,):
                    known_faces.append((face["person_id"], enc_arr))
        
        print(f"Loaded {len(known_faces)} known faces.")
        return known_faces

    def run(self):
        if not os.path.exists(self.import_dir):
            print(f"Import directory {self.import_dir} does not exist.")
            return

        processed_log = self.load_processed_log()
        processed_count = len(processed_log)
        
        if processed_count > 0:
            print(f"Resuming scan... Found {processed_count} previously processed images.")
        
        print("Scanning files...")
        candidates = []
        for root, dirs, files in os.walk(self.import_dir):
            rel_path = os.path.relpath(root, self.import_dir)
            
            folder_id = None
            if rel_path != '.':
                folder_id = self.get_or_create_folder(rel_path)
            
            for filename in files:
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
                    continue
                
                candidates.append((filename, file_path, folder_id, log_key))

        print(f"Found {len(candidates)} new images to process (skipped {processed_count} already processed).")
        if not candidates:
            return

        initial_faces = self.get_all_known_faces()

        # Resource Management Settings
        MAX_CPU_CORES = multiprocessing.cpu_count()
        MIN_WORKERS = 1
        MAX_WORKERS = max(1, MAX_CPU_CORES - 1)
        
        # Thresholds
        MEM_HIGH_THRESHOLD = 85.0 # Scale down if RAM > 85%
        MEM_LOW_THRESHOLD = 60.0  # Scale up if RAM < 60%
        CPU_HIGH_THRESHOLD = 90.0 # Don't scale up if CPU > 90%
        
        current_workers = 2 # Start conservative
        print(f"Starting with {current_workers} workers (Max: {MAX_WORKERS})...")

        ctx = multiprocessing.get_context('spawn')
        
        with ctx.Manager() as manager:
            new_faces_list = manager.list()
            
            task_queue = ctx.Queue()
            result_queue = ctx.Queue()
            
            # Fill queue
            for c in candidates:
                task_queue.put(c)
                
            total_tasks = len(candidates)
            
            workers = []
            
            def spawn_worker():
                p = ctx.Process(
                    target=worker_loop,
                    args=(task_queue, result_queue, initial_faces, new_faces_list, self.upload_enabled)
                )
                p.start()
                workers.append(p)
                return p

            # Initial spawn
            for _ in range(current_workers):
                spawn_worker()
                
            processed_count_session = 0
            pbar = tqdm(total=total_tasks, desc=f"Processing [{current_workers} workers]", unit="img", dynamic_ncols=True)
            
            last_scale_time = time.time()
            SCALE_COOLDOWN = 10 # Seconds between scaling actions
            
            try:
                while processed_count_session < total_tasks:
                    # Update progress bar description with current worker count
                    pbar.set_description(f"Processing [{len(workers)} workers]")
                    
                    # 1. Check for results
                    try:
                        while True:
                            # Non-blocking get
                            log_key, result = result_queue.get_nowait()
                            
                            if result:
                                thumb_filename, faces_info = result[1:] # result is (rel_path, thumb, faces)
                                log_entry = {
                                    "processed_at": datetime.now(timezone.utc).isoformat(),
                                    "thumbnail": thumb_filename,
                                    "faces": faces_info
                                }
                                processed_log[log_key] = log_entry
                                self.append_to_log(log_key, log_entry)
                            
                            processed_count_session += 1
                            pbar.update(1)
                    except queue.Empty:
                        pass
                    
                    # 2. Monitor Workers (Restart dead ones)
                    active_workers = []
                    for p in workers:
                        if p.is_alive():
                            active_workers.append(p)
                        else:
                            # Worker died
                            pbar.write(f"Worker {p.pid} died. Respawning...")
                            # Don't remove from list yet, we'll replace it
                            spawn_worker()
                            # Note: The dead worker is dropped from active_workers
                    
                    workers = [p for p in workers if p.is_alive()]
                    
                    # 3. Dynamic Scaling
                    now = time.time()
                    if now - last_scale_time > SCALE_COOLDOWN:
                        mem_percent = psutil.virtual_memory().percent
                        cpu_percent = psutil.cpu_percent(interval=None)
                        
                        # Scale Down
                        if mem_percent > MEM_HIGH_THRESHOLD and len(workers) > MIN_WORKERS:
                            pbar.write(f"High Memory ({mem_percent}%)! Scaling down...")
                            # Kill one worker
                            victim = workers.pop()
                            victim.terminate()
                            victim.join(timeout=2)
                            if victim.is_alive(): victim.kill()
                            last_scale_time = now
                            
                        # Scale Up
                        elif mem_percent < MEM_LOW_THRESHOLD and cpu_percent < CPU_HIGH_THRESHOLD and len(workers) < MAX_WORKERS:
                            # Only scale up if we have enough tasks pending
                            # Approximate pending tasks
                            if (total_tasks - processed_count_session) > len(workers) * 2:
                                pbar.write(f"Resources available (Mem: {mem_percent}%, CPU: {cpu_percent}%). Scaling up...")
                                spawn_worker()
                                last_scale_time = now
                    
                    time.sleep(0.1)
                    
            except KeyboardInterrupt:
                pbar.write("\nStopping...")
            finally:
                pbar.close()
                pbar.write("Cleaning up workers...")
                for p in workers:
                    p.terminate()
                    p.join(timeout=2)
                    if p.is_alive(): p.kill()
                
                # Close queues
                task_queue.close()
                result_queue.close()
                task_queue.join_thread()
                result_queue.join_thread()
            
        print(f"Processed {processed_count_session} new images.")

    def process_pending_uploads(self):
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
                continue
                
            file_path = os.path.join(self.import_dir, relative_path)
            if not os.path.exists(file_path):
                continue
                
            try:
                with open(file_path, 'rb') as f:
                    image_bytes = f.read()
                
                unique_filename = image["filename"]
                mime_type = image.get("mime_type", "application/octet-stream")
                
                self.storage.upload_bytes(image_bytes, unique_filename, mime_type)
                
                thumb_filename = image.get("thumbnail_path")
                if not thumb_filename:
                    thumb_filename = f"thumb_{unique_filename}"
                
                local_thumb_path = os.path.join(settings.thumbnail_dir, thumb_filename)
                if os.path.exists(local_thumb_path):
                    with open(local_thumb_path, 'rb') as f:
                        self.storage.upload_fileobj(f, thumb_filename, mime_type)
                else:
                    thumb_io = create_thumbnail(image_bytes)
                    self.storage.upload_fileobj(thumb_io, thumb_filename, mime_type)
                
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
                
            except Exception as e:
                print(f"Error uploading {relative_path}: {e}")
                
        print(f"Uploaded {count} pending images.")

def run_batch_processor(upload_enabled=True, upload_only=False):
    processor = BatchProcessor(upload_enabled=upload_enabled)
    if upload_only:
        processor.process_pending_uploads()
    else:
        processor.run()
