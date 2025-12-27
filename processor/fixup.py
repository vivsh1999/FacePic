#!/usr/bin/env python3
import os
import sys
import argparse
import numpy as np
from tqdm import tqdm
from bson import ObjectId

# Add the current directory to python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import get_sync_database
from app.config import get_settings
from app.services.storage_service import get_storage_service
from PIL import Image, ImageOps
import io

def prune_faces(db, min_score=0.65, edge_margin=10):
    print("Pruning faces...")
    storage = get_storage_service()
    
    # Get all faces
    faces = list(db.faces.find({}))
    print(f"Found {len(faces)} faces total.")
    
    removed_count = 0
    
    # Cache image dimensions to avoid repeated lookups
    image_dims = {}
    
    for face in tqdm(faces, desc="Checking faces"):
        face_id = face["_id"]
        image_id = face["image_id"]
        person_id = face.get("person_id")
        
        # Get image dimensions
        if image_id not in image_dims:
            image = db.images.find_one({"_id": image_id})
            if image:
                image_dims[image_id] = (image["width"], image["height"])
            else:
                # Image not found? Skip
                continue
        
        width, height = image_dims[image_id]
        
        should_remove = False
        reason = ""
        
        # Check score if available
        if "metadata" in face and face["metadata"] and "det_score" in face["metadata"]:
            score = face["metadata"]["det_score"]
            if score < min_score:
                should_remove = True
                reason = f"Low score: {score:.3f}"
        
        # Check edges
        if not should_remove:
            loc = face["location"]
            # location is top, right, bottom, left
            top, right, bottom, left = loc["top"], loc["right"], loc["bottom"], loc["left"]
            
            if (left < edge_margin or 
                top < edge_margin or 
                right > width - edge_margin or 
                bottom > height - edge_margin):
                should_remove = True
                reason = "Partial face (edge)"
        
        if should_remove:
            # Delete face
            db.faces.delete_one({"_id": face_id})
            
            # Remove from image's faces list
            db.images.update_one(
                {"_id": image_id},
                {"$pull": {"faces": face_id}}
            )
            
            # Check if person has any other faces
            if person_id:
                other_faces = db.faces.count_documents({"person_id": person_id})
                if other_faces == 0:
                    # Person is empty, delete person and thumbnail
                    db.persons.delete_one({"_id": ObjectId(person_id)})
                    
                    # Delete thumbnail
                    if "thumbnail_path" in face and face["thumbnail_path"]:
                        thumb_path = face["thumbnail_path"]
                        # Local delete
                        if os.path.exists(thumb_path):
                            try:
                                os.remove(thumb_path)
                            except OSError:
                                pass
                        
                        # R2 delete (filename is usually faces/person_ID.jpg)
                        # Extract filename from path
                        filename = os.path.basename(thumb_path)
                        storage.delete_file(f"faces/{filename}")
            
            removed_count += 1
            
    print(f"Removed {removed_count} faces.")

def merge_duplicate_persons(db, tolerance=None):
    settings = get_settings()
    storage = get_storage_service()
    if tolerance is None:
        tolerance = settings.insightface_tolerance
    
    print(f"Merging duplicate persons (tolerance={tolerance})...")
    
    # Get all persons
    persons = list(db.persons.find({}))
    print(f"Found {len(persons)} persons.")
    
    person_encodings = {}
    person_names = {}
    
    for person in tqdm(persons, desc="Loading person data"):
        pid = str(person["_id"])
        person_names[pid] = person.get("name")
        
        # Get representative face
        rep_face_id = person.get("representative_face_id")
        face = None
        
        if rep_face_id:
            face = db.faces.find_one({"_id": ObjectId(rep_face_id)})
        
        # Fallback: get any face if representative not found
        if not face:
            face = db.faces.find_one({"person_id": pid})
            
        if face and "encoding" in face:
            person_encodings[pid] = np.array(face["encoding"])
    
    # Compare and merge
    merged_count = 0
    processed_ids = set()
    
    pids = list(person_encodings.keys())
    
    for i in tqdm(range(len(pids)), desc="Comparing persons"):
        id1 = pids[i]
        if id1 in processed_ids:
            continue
            
        enc1 = person_encodings[id1]
        
        # Find all matches for this person
        matches = []
        for j in range(i + 1, len(pids)):
            id2 = pids[j]
            if id2 in processed_ids:
                continue
                
            enc2 = person_encodings[id2]
            
            # Check dimensions
            if len(enc1) != len(enc2):
                continue
                
            # Calculate distance
            if len(enc1) == 512:
                # InsightFace: Cosine distance
                similarity = np.dot(enc1, enc2)
                distance = 1 - similarity
            else:
                # face-api.js: Euclidean distance
                distance = np.linalg.norm(enc1 - enc2)
            
            if distance < tolerance:
                matches.append(id2)
        
        if matches:
            # Merge matches into id1
            target_id = id1
            target_name = person_names[target_id]
            
            for source_id in matches:
                if source_id in processed_ids:
                    continue
                    
                source_name = person_names[source_id]
                
                # Conflict check
                if target_name and source_name and target_name != source_name:
                    # print(f"Skipping merge of {target_name} and {source_name}: Name conflict")
                    continue
                
                # Determine direction
                final_target = target_id
                final_source = source_id
                
                if not target_name and source_name:
                    # Merge unnamed into named
                    final_target = source_id
                    final_source = target_id
                    target_id = source_id # Update current target
                    target_name = source_name
                
                # Perform merge
                # Move faces
                db.faces.update_many(
                    {"person_id": final_source},
                    {"$set": {"person_id": final_target}}
                )
                
                # Update thumbnail paths for moved faces to point to target's thumbnail
                # This ensures consistency
                target_thumb_filename = f"person_{final_target}.jpg"
                target_thumb_path = os.path.join(settings.thumbnail_dir, "faces", target_thumb_filename)
                
                db.faces.update_many(
                    {"person_id": final_target},
                    {"$set": {"thumbnail_path": target_thumb_path}}
                )
                
                # Delete source person
                db.persons.delete_one({"_id": ObjectId(final_source)})
                
                # Delete source thumbnail
                source_thumb_filename = f"person_{final_source}.jpg"
                source_thumb_path = os.path.join(settings.thumbnail_dir, "faces", source_thumb_filename)
                
                if os.path.exists(source_thumb_path):
                    try:
                        os.remove(source_thumb_path)
                    except OSError:
                        pass
                
                storage.delete_file(f"faces/{source_thumb_filename}")
                
                processed_ids.add(final_source)
                merged_count += 1
                
    print(f"Merged {merged_count} persons.")

def fix_orientation(db):
    print("Fixing face thumbnail orientation...")
    settings = get_settings()
    storage = get_storage_service()
    
    # Get all persons
    persons = list(db.persons.find({}))
    
    for person in tqdm(persons, desc="Processing persons"):
        person_id = str(person["_id"])
        
        # Find the best face (highest score)
        best_face = db.faces.find_one(
            {"person_id": person_id},
            sort=[("metadata.det_score", -1)]
        )
        
        if not best_face:
            continue
            
        image_id = best_face["image_id"]
        image = db.images.find_one({"_id": image_id})
        
        if not image:
            continue
            
        # Construct path to original image
        # Assuming import_dir structure
        if "relative_path" in image:
            image_path = os.path.join(settings.import_dir, image["relative_path"])
        else:
            continue
            
        if not os.path.exists(image_path):
            continue
            
        try:
            # Open and fix orientation
            with open(image_path, 'rb') as f:
                img_bytes = f.read()
                
            img = Image.open(io.BytesIO(img_bytes))
            img = ImageOps.exif_transpose(img)
            
            # Crop face
            loc = best_face["location"]
            top, right, bottom, left = loc["top"], loc["right"], loc["bottom"], loc["left"]
            
            # Ensure bounds
            width, height = img.size
            left = max(0, left)
            top = max(0, top)
            right = min(width, right)
            bottom = min(height, bottom)
            
            face_img = img.crop((left, top, right, bottom))
            
            # Save thumbnail
            thumb_filename = f"person_{person_id}.jpg"
            local_thumb_path = os.path.join(settings.thumbnail_dir, "faces", thumb_filename)
            
            os.makedirs(os.path.dirname(local_thumb_path), exist_ok=True)
            
            face_img.save(local_thumb_path, format="JPEG", quality=85)
            
            # Upload to R2
            thumb_io = io.BytesIO()
            face_img.save(thumb_io, format="JPEG", quality=85)
            thumb_io.seek(0)
            
            storage.upload_fileobj(thumb_io, f"faces/{thumb_filename}", "image/jpeg")
            
        except Exception as e:
            print(f"Error fixing orientation for person {person_id}: {e}")

def main():
    parser = argparse.ArgumentParser(description="Fixup faces and persons.")
    parser.add_argument("--skip-prune", action="store_true", help="Skip pruning faces.")
    parser.add_argument("--skip-merge", action="store_true", help="Skip merging persons.")
    parser.add_argument("--fix-orientation", action="store_true", help="Fix orientation of face thumbnails.")
    parser.add_argument("--tolerance", type=float, help="Override clustering tolerance (default: from config).")
    
    args = parser.parse_args()
    
    db = get_sync_database()
    
    if not args.skip_prune:
        prune_faces(db)
    
    if not args.skip_merge:
        merge_duplicate_persons(db, tolerance=args.tolerance)
        
    if args.fix_orientation:
        fix_orientation(db)

if __name__ == "__main__":
    main()
