from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient
import os
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# MongoDB settings
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "web_scraper_db")

# Async MongoDB client (for FastAPI)
client: AsyncIOMotorClient = None
database = None


async def connect_to_mongo():
    """Connect to MongoDB on application startup"""
    global client, database
    try:
        client = AsyncIOMotorClient(MONGODB_URL)
        database = client[DATABASE_NAME]
        # Test the connection
        await client.admin.command('ping')
        logger.info(f"✅ Connected to MongoDB at {MONGODB_URL}")
        logger.info(f"✅ Using database: {DATABASE_NAME}")
    except Exception as e:
        logger.error(f"❌ Could not connect to MongoDB: {e}")
        raise


async def close_mongo_connection():
    """Close MongoDB connection on application shutdown"""
    global client
    if client:
        client.close()
        logger.info("✅ MongoDB connection closed")


def get_database():
    """Get database instance"""
    return database