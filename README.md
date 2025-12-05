# 📸 ImageTag - Smart Photo People Tagging & Grouping

A Google Photos-like application that automatically detects faces in your photos, groups them by person, and lets you label each person to browse photos organized by people.

## ✨ Features

- **Bulk Image Upload**: Upload multiple images at once
- **Automatic Face Detection**: Detect all faces in uploaded photos
- **Face Clustering**: Automatically group similar faces together
- **Person Labeling**: Name each person for easy identification
- **Photo Browsing by Person**: View all photos of a specific person
- **Merge Clusters**: Manually merge incorrectly split person clusters

## 🏗️ Architecture

### Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | React + TypeScript + Tailwind CSS |
| Backend | Python FastAPI |
| Face Detection/Recognition | `face_recognition` library (dlib) |
| Database | SQLite (SQLAlchemy ORM) |
| Image Storage | Local filesystem |

### System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Frontend (React)                        │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────────────┐ │
│  │ Upload  │  │ Gallery │  │ People  │  │ Person Details  │ │
│  │  Page   │  │  View   │  │  List   │  │    (Photos)     │ │
│  └─────────┘  └─────────┘  └─────────┘  └─────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Backend (FastAPI)                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   Upload    │  │    Face     │  │   Person/Label      │  │
│  │   Service   │  │  Detection  │  │    Management       │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      Data Layer                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   SQLite    │  │   Image     │  │   Face Encodings    │  │
│  │  Database   │  │   Storage   │  │   (128-d vectors)   │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Database Schema

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   images     │     │    faces     │     │   persons    │
├──────────────┤     ├──────────────┤     ├──────────────┤
│ id           │◄────│ image_id     │     │ id           │
│ filename     │     │ id           │────►│ name         │
│ filepath     │     │ person_id    │     │ created_at   │
│ uploaded_at  │     │ encoding     │     └──────────────┘
│ thumbnail    │     │ bbox (x,y,w,h)│
└──────────────┘     │ thumbnail    │
                     └──────────────┘
```

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/upload` | Upload multiple images |
| `GET` | `/api/images` | List all images |
| `GET` | `/api/images/{id}` | Get image details with faces |
| `DELETE` | `/api/images/{id}` | Delete an image |
| `GET` | `/api/persons` | List all detected persons |
| `GET` | `/api/persons/{id}` | Get person details |
| `PUT` | `/api/persons/{id}` | Update person name/label |
| `POST` | `/api/persons/merge` | Merge two person clusters |
| `GET` | `/api/persons/{id}/photos` | Get all photos of a person |
| `POST` | `/api/process` | Trigger face detection on pending images |

### Face Recognition Flow

```
1. Image Upload
       │
       ▼
2. Face Detection (find faces in image)
       │
       ▼
3. Face Encoding (generate 128-dimensional vector per face)
       │
       ▼
4. Face Clustering (group similar encodings using distance threshold)
       │
       ▼
5. Create/Update Person records
       │
       ▼
6. User Labels persons with names
```

## 📁 Project Structure

```
ImageTag/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI application entry
│   │   ├── config.py            # Configuration settings
│   │   ├── database.py          # Database connection & session
│   │   ├── models.py            # SQLAlchemy ORM models
│   │   ├── schemas.py           # Pydantic request/response schemas
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── face_service.py  # Face detection & recognition
│   │   │   ├── image_service.py # Image processing & thumbnails
│   │   │   └── clustering_service.py  # Face clustering logic
│   │   └── routers/
│   │       ├── __init__.py
│   │       ├── images.py        # Image-related endpoints
│   │       └── persons.py       # Person-related endpoints
│   ├── uploads/                 # Stored original images
│   ├── thumbnails/              # Generated thumbnails
│   │   ├── images/              # Image thumbnails
│   │   └── faces/               # Face crop thumbnails
│   ├── requirements.txt         # Python dependencies
│   └── .env.example             # Environment variables template
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── ImageUpload.tsx  # Bulk upload component
│   │   │   ├── Gallery.tsx      # Photo gallery grid
│   │   │   ├── PersonList.tsx   # List of detected persons
│   │   │   ├── PersonPhotos.tsx # Photos of a specific person
│   │   │   ├── FaceTag.tsx      # Face tag overlay on images
│   │   │   └── PersonLabel.tsx  # Editable person name
│   │   ├── pages/
│   │   │   ├── HomePage.tsx
│   │   │   ├── UploadPage.tsx
│   │   │   ├── GalleryPage.tsx
│   │   │   ├── PeoplePage.tsx
│   │   │   └── PersonDetailPage.tsx
│   │   ├── services/
│   │   │   └── api.ts           # API client
│   │   ├── types/
│   │   │   └── index.ts         # TypeScript interfaces
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── package.json
│   ├── tsconfig.json
│   ├── tailwind.config.js
│   └── vite.config.ts
├── README.md
└── .gitignore
```

## 🚀 Getting Started

### Prerequisites

- **Python 3.9+**
- **Node.js 18+**
- **CMake** (required for dlib/face_recognition)

#### Installing CMake (macOS)
```bash
brew install cmake
```

#### Installing CMake (Ubuntu/Debian)
```bash
sudo apt-get install cmake
```

### Backend Setup

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Run the development server:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

The API will be available at `http://localhost:8000`

API Documentation: `http://localhost:8000/docs`

### Frontend Setup

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Run the development server:
   ```bash
   npm run dev
   ```

The app will be available at `http://localhost:5173`

## 🔧 Configuration

### Backend Environment Variables

Create a `.env` file in the `backend/` directory:

```env
# Database
DATABASE_URL=sqlite:///./imagetag.db

# Storage paths
UPLOAD_DIR=./uploads
THUMBNAIL_DIR=./thumbnails

# Face recognition settings
FACE_RECOGNITION_TOLERANCE=0.6  # Lower = stricter matching
FACE_RECOGNITION_MODEL=hog      # 'hog' (faster) or 'cnn' (more accurate)

# Server settings
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
```

## 🚀 Implementation Phases

### Phase 1: Backend Foundation ✅
- [x] Set up FastAPI project structure
- [x] Create database models (SQLite + SQLAlchemy)
- [x] Implement image upload endpoint
- [x] Set up image storage

### Phase 2: Face Detection & Recognition ✅
- [x] Integrate face_recognition library
- [x] Implement face detection service
- [x] Generate face encodings (128-dimensional vectors)
- [x] Implement face clustering algorithm

### Phase 3: Person Management ✅
- [x] Auto-group similar faces into persons
- [x] API for labeling persons with names
- [x] API for merging person clusters
- [x] Get photos by person endpoint

### Phase 4: Frontend ✅
- [x] Set up React + TypeScript + Tailwind
- [x] Bulk image upload component with drag & drop
- [x] Image gallery view with infinite scroll
- [x] Person list with face thumbnails
- [x] Person detail page with their photos
- [x] Label editing interface

### Phase 5: Polish ✅
- [x] Loading states and error handling
- [x] Thumbnail generation optimization
- [x] Background processing for large uploads
- [x] UI/UX improvements (infinite scroll, search, progress indicators)

## 📚 How It Works

### Face Recognition Pipeline

1. **Detection**: When images are uploaded, the system uses dlib's HOG-based face detector (or CNN for better accuracy) to locate all faces in each image.

2. **Encoding**: Each detected face is converted into a 128-dimensional vector (face encoding) that represents the unique features of that face.

3. **Clustering**: Face encodings are compared using Euclidean distance. Faces with distance < 0.6 (configurable tolerance) are considered the same person.

4. **Grouping**: Similar faces are grouped into "Person" entities. Initially unnamed, users can label them.

5. **Matching**: When new images are uploaded, detected faces are compared against existing person encodings to find matches.

### Distance Calculation

The face_recognition library uses a 128-dimensional encoding. Two faces are considered a match if:

```
euclidean_distance(encoding1, encoding2) < tolerance
```

Default tolerance: `0.6`
- Lower values = stricter matching (fewer false positives)
- Higher values = looser matching (fewer false negatives)

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

This project is licensed under the MIT License.
