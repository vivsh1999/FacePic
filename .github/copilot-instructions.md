# FacePic AI Coding Instructions

## 1. Project Overview
FacePic is a Google Photos-like application for face detection, clustering, and photo organization.
- **Stack:** React (Vite) + Python (FastAPI) + MongoDB Atlas.
- **Infrastructure:** AWS (ECR, S3, CloudFront) + Cloudflare, managed via Terraform.
- **Core Feature:** Hybrid face detection (Client-side `face-api.js` or Server-side `face_recognition`/`insightface`).

## 2. Architecture & Patterns

### Backend (`backend/`)
- **Framework:** FastAPI with `motor` (async) and `pymongo` (sync) drivers.
- **Database Pattern:**
  - Use `backend/app/database.py` for DB access.
  - `get_database()` returns `AsyncIOMotorDatabase` for API endpoints.
  - `get_sync_database()` returns `Database` for background tasks/scripts.
- **Service Layer:** Logic resides in `backend/app/services/`.
  - `face_service.py`: Handles face detection logic. Note the fallback: if `face_recognition` lib is missing, it expects client-side detection.
- **Configuration:** Settings managed in `backend/app/config.py` using Pydantic.

### Frontend (`frontend/`)
- **Framework:** React + TypeScript + Vite + Tailwind CSS.
- **API Layer:** `frontend/src/services/api.ts` wraps `axios`.
  - Base URL is `/api` (proxied in dev, configured in prod).
  - `uploadImagesServerDetect` vs `uploadImages` (client-side detection).
- **State:** Local state mostly; complex data flows via props/context.

### Infrastructure (`iac/`)
- **Tool:** Terraform (`iac/terraform/`).
- **State:** Managed in AWS S3 (backend).
- **Deployment:** GitHub Actions (`.github/workflows/deploy.yml`) builds Docker images and runs `terraform apply`.

## 3. Critical Workflows

### Local Development
- **Start:** `docker-compose up` (starts Backend, Frontend, MongoDB).
- **Frontend Dev:** `cd frontend && npm run dev` (runs on port 4173).
- **Backend Dev:** `cd backend && uvicorn app.main:app --reload` (runs on port 8000).

### Deployment
- **Trigger:** Push to `main` branch.
- **Process:**
  1. Build & Push Backend Docker Image to ECR.
  2. Run Terraform to update infrastructure (ECS/App Runner, S3, CloudFront).
  3. Build Frontend & Sync to S3.

## 4. Coding Conventions
- **No Tests:** The project currently lacks a test suite. Focus on manual verification and defensive coding.
- **Async First:** Prefer `async/await` in Backend routes and Frontend API calls.
- **Type Safety:** Enforce Pydantic models in Backend and TypeScript interfaces in Frontend (`frontend/src/types/index.ts`).
- **Face Data:** Face encodings are stored as binary/arrays. Handle conversions carefully (`encoding_utils.py`).

## 5. Key Files
- `backend/app/main.py`: App entry & lifespan (DB init).
- `backend/app/database.py`: DB connection factory.
- `frontend/src/services/api.ts`: API client definitions.
- `iac/terraform/main.tf`: Main infrastructure definition.
