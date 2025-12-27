"""MongoDB database connection and utilities."""
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import MongoClient
from bson import ObjectId
from typing import Optional
import asyncio

from .config import get_settings

settings = get_settings()

# Async client for FastAPI endpoints
_async_client: Optional[AsyncIOMotorClient] = None
_async_db: Optional[AsyncIOMotorDatabase] = None

# Sync client for background tasks
_sync_client: Optional[MongoClient] = None
_sync_db = None


def get_mongo_client() -> AsyncIOMotorClient:
    """Get the async MongoDB client."""
    global _async_client
    if _async_client is None:
        _async_client = AsyncIOMotorClient(settings.mongodb_url)
    return _async_client


def get_database() -> AsyncIOMotorDatabase:
    """Get the async database instance."""
    global _async_db
    if _async_db is None:
        client = get_mongo_client()
        _async_db = client[settings.mongodb_database]
    return _async_db


def get_sync_database():
    """Get synchronous database for background tasks."""
    global _sync_client, _sync_db
    if _sync_client is None:
        _sync_client = MongoClient(settings.mongodb_url)
        _sync_db = _sync_client[settings.mongodb_database]
    return _sync_db


async def get_db() -> AsyncIOMotorDatabase:
    """Dependency to get database instance."""
    return get_database()


async def init_db() -> None:
    """Initialize database indexes."""
    db = get_database()
    
    # Create indexes for images collection
    await db.images.create_index("filename")
    await db.images.create_index("uploaded_at")
    await db.images.create_index("processed")
    
    # Create indexes for faces collection
    await db.faces.create_index("image_id")
    await db.faces.create_index("person_id")
    
    # Create indexes for persons collection
    await db.persons.create_index("name")
    await db.persons.create_index("created_at")


async def close_db() -> None:
    """Close database connections."""
    global _async_client, _sync_client
    if _async_client:
        _async_client.close()
        _async_client = None
    if _sync_client:
        _sync_client.close()
        _sync_client = None


# Helper functions for ObjectId conversion
def to_object_id(id_str: str) -> Optional[ObjectId]:
    """Convert string to ObjectId, return None if invalid."""
    try:
        return ObjectId(id_str)
    except:
        return None


def str_id(doc: dict) -> dict:
    """Convert _id to string id in a document."""
    if doc and "_id" in doc:
        doc["id"] = str(doc["_id"])
        del doc["_id"]
    return doc

