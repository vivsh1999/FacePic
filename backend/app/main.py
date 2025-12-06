"""FastAPI application entry point."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from .config import get_settings
from .database import init_db, close_db, get_database
from .routers import images, persons

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    # Startup
    await init_db()
    settings.setup_directories()
    yield
    # Shutdown
    await close_db()


# Create FastAPI app
app = FastAPI(
    title="ImageTag API",
    description="Smart photo tagging and people grouping API",
    version="1.0.0",
    lifespan=lifespan,
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
    db = get_database()
    
    total_images = await db.images.count_documents({})
    total_faces = await db.faces.count_documents({})
    total_persons = await db.persons.count_documents({})
    labeled_persons = await db.persons.count_documents({"name": {"$ne": None}})
    
    return {
        "total_images": total_images,
        "total_faces": total_faces,
        "total_persons": total_persons,
        "labeled_persons": labeled_persons,
        "unlabeled_persons": total_persons - labeled_persons,
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
