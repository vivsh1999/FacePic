"""FastAPI application entry point."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .database import init_db
from .routers import images, persons
from .models import Image, Person, Face  # Import models to register them

settings = get_settings()

# Create FastAPI app
app = FastAPI(
    title="ImageTag API",
    description="Smart photo tagging and people grouping API",
    version="1.0.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(images.router)
app.include_router(persons.router)


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    init_db()
    settings.setup_directories()


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "ImageTag API",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/api/stats")
async def get_stats():
    """Get overall statistics."""
    from sqlalchemy.orm import Session
    from .database import SessionLocal
    
    db = SessionLocal()
    try:
        total_images = db.query(Image).count()
        total_faces = db.query(Face).count()
        total_persons = db.query(Person).count()
        labeled_persons = db.query(Person).filter(Person.name.isnot(None)).count()
        
        return {
            "total_images": total_images,
            "total_faces": total_faces,
            "total_persons": total_persons,
            "labeled_persons": labeled_persons,
            "unlabeled_persons": total_persons - labeled_persons,
        }
    finally:
        db.close()


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
