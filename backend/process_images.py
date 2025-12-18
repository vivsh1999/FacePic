#!/usr/bin/env python3
"""
Entry point for batch processing of images.
This script scans the import directory, processes new images,
detects faces, uploads to R2, and updates the database.
"""
import os
import sys
import argparse

# Suppress ONNX Runtime logs (must be before any imports)
os.environ["ORT_LOGGING_LEVEL"] = "3"

# Add the current directory to python path to allow imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.batch_processor import run_batch_processor

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Batch process images for FacePic.")
    parser.add_argument("--disable-upload", action="store_true", help="Disable uploading to R2 (process only).")
    parser.add_argument("--upload-only", action="store_true", help="Only upload pending images (skip processing new ones).")
    
    args = parser.parse_args()
    
    upload_enabled = not args.disable_upload
    upload_only = args.upload_only
    
    if args.disable_upload and args.upload_only:
        print("Error: Cannot use --disable-upload and --upload-only together.")
        sys.exit(1)

    run_batch_processor(upload_enabled=upload_enabled, upload_only=upload_only)
