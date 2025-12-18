#!/usr/bin/env python3
import os
import sys
import shutil
import argparse

# Add the current directory to python path to allow imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.config import get_settings
from app.database import get_sync_database

def cleanup(force=False):
    settings = get_settings()
    db = get_sync_database()
    
    if not force:
        print("WARNING: This will delete ALL processed data (DB records, thumbnails, logs).")
        print(f"Database: {settings.mongodb_database}")
        print(f"Uploads: {settings.upload_dir}")
        print(f"Thumbnails: {settings.thumbnail_dir}")
        confirm = input("Are you sure? (y/N): ")
        if confirm.lower() != 'y':
            print("Aborted.")
            return

    print("Cleaning database...")
    # Delete all documents from collections
    db.images.delete_many({})
    db.faces.delete_many({})
    db.persons.delete_many({})
    db.folders.delete_many({})
    print("Database collections cleared.")

    print("Cleaning files...")
    
    # Clean thumbnails
    if os.path.exists(settings.thumbnail_dir):
        for filename in os.listdir(settings.thumbnail_dir):
            file_path = os.path.join(settings.thumbnail_dir, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                print(f"Failed to delete {file_path}. Reason: {e}")
        print(f"Cleared {settings.thumbnail_dir}")

    # Clean uploads (but keep directory)
    if os.path.exists(settings.upload_dir):
        for filename in os.listdir(settings.upload_dir):
            file_path = os.path.join(settings.upload_dir, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                print(f"Failed to delete {file_path}. Reason: {e}")
        print(f"Cleared {settings.upload_dir}")

    # The processed_log_file is usually inside upload_dir, so it might be gone already.
    # But let's be explicit just in case it's configured elsewhere.
    log_file = settings.processed_log_file
    if os.path.exists(log_file):
        try:
            os.remove(log_file)
            print(f"Deleted log file: {log_file}")
        except Exception as e:
            print(f"Error deleting log file {log_file}: {e}")
    else:
        print(f"Log file not found at: {log_file}")

    print("Cleanup complete.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cleanup FacePic data.")
    parser.add_argument("--force", action="store_true", help="Skip confirmation prompt.")
    args = parser.parse_args()
    
    cleanup(args.force)
