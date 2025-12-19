# FacePic Image Processing Architecture

## Overview
FacePic uses a hybrid "Personal Cloud" architecture where heavy image processing (face detection) happens locally on your machine, while storage and metadata are managed in the cloud. This ensures privacy, reduces cloud compute costs, and leverages local hardware.

## Components

### 1. Local Environment (Docker)
- **Container**: `facepic-backend` (Python 3.12)
- **Script**: `backend/process_images.py`
- **Input Source**: Local directory or external drive mounted to `/app/import_images` inside the container.
- **State Tracking**: `processed_log.jsonl` (JSON Lines format) tracks processed files to support resuming and idempotency.
- **Caching**: Docker BuildKit cache and local pip cache (`dockercache/`) for fast rebuilds.

### 2. Face Detection Engine
- **Library**: [InsightFace](https://github.com/deepinsight/insightface)
- **Model**: `buffalo_l` (ResNet50-based)
- **Execution**: CPU (via ONNX Runtime). Optimized for Apple Silicon (M1/M2) via `onnxruntime-silicon` when running natively, or standard `onnxruntime` in Docker.
- **Output**: 
  - 512-dimensional face embeddings
  - Bounding box coordinates
  - Facial landmarks (used for alignment)
  - **Best Face Selection**: Automatically updates the representative thumbnail for a person if a higher-quality face is detected.

### 3. Cloud Storage (Cloudflare R2)
- **Bucket**: `facepic`
- **Protocol**: S3-compatible API (via `boto3`)
- **Stored Assets**:
  - **Originals**: Uploaded with a UUID filename (e.g., `a1b2c3d4.jpg`).
  - **Thumbnails**: Generated locally (300x300px) and uploaded as `thumb_<uuid>.jpg`.
  - **Face Thumbnails**: Cropped face images stored as `faces/person_<person_id>.jpg`.

### 4. Database (MongoDB Atlas)
- **Database**: `facepic`
- **Schemas**:
  - **Images**: Stores metadata (filename, R2 path, dimensions, upload timestamp, EXIF/GPS data, and a redundant list of `faces`).
  - **Faces**: Stores face encodings (vector), bounding boxes, and links to `Image` and `Person`.
  - **Persons**: Represents a unique identity (cluster of faces).
  - **Folders**: Mirrors the local directory structure for organization.

## Data Flow

1.  **Ingestion**:
    - User mounts photos to the container (e.g., from external SSD).
    - User runs `./run_processor.sh` (supports `--disable-upload` and `--upload-only`).

2.  **Processing Loop**:
    - The script recursively scans the import directory.
    - Checks `processed_log.jsonl`. If file is present in log, it skips.
    - If new:
        1.  **Read**: Loads image into memory.
        2.  **Detect**: InsightFace extracts face locations and embeddings.
        3.  **Thumbnail Generation**:
            - Generates main image thumbnail.
            - Crops face thumbnails.
            - **Deduplication**: Reuses existing face thumbnail if one exists for the matched person.
            - **Upgrade**: Overwrites face thumbnail if the new face has a higher detection score.
        4.  **Upload (Optional)**: Streams original image and thumbnails to Cloudflare R2 (if enabled).
        5.  **Index**:
            - Creates `Image` document in MongoDB with EXIF/GPS metadata.
            - For each face:
                - Compares embedding with existing `Person` clusters (Cosine Similarity).
                - Matches to existing `Person` OR creates a new `Person`.
                - Creates `Face` document linked to the Image and Person.
            - **Redundancy**: Updates the `Image` document with the list of all `faces` detected in it.
        6.  **Log**: Appends entry to `processed_log.jsonl`.

## Directory Structure

```
FacePic/
├── backend/
│   ├── app/                # Application code
│   ├── uploads/            # [Local] Log file (processed_log.jsonl)
│   ├── thumbnails/         # [Local] Generated thumbnails
│   │   └── faces/          # [Local] Cropped face thumbnails
│   ├── process_images.py   # CLI Entry point
│   └── cleanup.py          # Data wipe tool
├── dockercache/            # [Local] Pip cache persistence
├── docker-compose.yml      # [Config] Production setup
└── .env                    # [Config] Credentials (R2, Mongo)
```

## Key Algorithms

### Face Matching
- **Metric**: Cosine Similarity.
- **Threshold**: `0.4` (configurable).
- **Logic**: A new face is compared against all known faces of existing persons. If the maximum similarity exceeds the threshold, it is assigned to that person. Otherwise, a new person ID is generated.

### Idempotency & Resuming
- **Log Format**: `processed_log.jsonl` (Append-only JSON Lines).
- **Resume**: On startup, the script reads the log to build an in-memory set of processed files.
- **Crash Recovery**: Since the log is append-only, an interruption only affects the last entry. The next run resumes from the last successful file.

### CLI Features
- `--disable-upload`: Process images and save metadata/thumbnails locally without uploading to R2.
- `--upload-only`: Scan for processed images that haven't been uploaded yet and upload them.
- **Progress Bars**: Real-time visual feedback using `tqdm`.
