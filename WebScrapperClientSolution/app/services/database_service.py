from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging
from bson import ObjectId

logger = logging.getLogger(__name__)


class DatabaseService:
    """Service for MongoDB operations"""

    def __init__(self, database: AsyncIOMotorDatabase):
        self.db = database
        self.collection = self.db.scraped_pages
        logger.info("DatabaseService initialized")

    async def create_indexes(self):
        """Create indexes for better query performance"""
        try:
            # Index on URL for faster lookups
            await self.collection.create_index("url")
            # Index on scraped_at for time-based queries
            await self.collection.create_index("scraped_at")

            # --- ADD THIS: Create a text index for the KB content ---
            await self.collection.create_index(
                [("kb_content", "text")],
                name="kb_content_text_index",
                default_language="italian"  # Change if you scrape other languages
            )
            # ---------------------------------------------------------

            logger.info("Database indexes created")
        except Exception as e:
            logger.error(f"Failed to create indexes: {e}")

    async def save_scraped_data(self, scraped_data: Dict[str, Any]) -> str:
        """
        Save scraped data to MongoDB

        Args:
            scraped_data: Dictionary containing scraped content

        Returns:
            str: The inserted document ID
        """
        try:
            # Insert the document
            result = await self.collection.insert_one(scraped_data)

            logger.info(f"Saved to MongoDB with ID: {result.inserted_id}")

            return str(result.inserted_id)

        except Exception as e:
            logger.error(f"Failed to save to MongoDB: {e}")
            raise Exception(f"Database save failed: {str(e)}")

    async def get_scraped_data_by_id(self, document_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve scraped data by document ID

        Args:
            document_id: MongoDB document ID

        Returns:
            Document data or None if not found
        """
        try:
            if not ObjectId.is_valid(document_id):
                return None

            document = await self.collection.find_one({"_id": ObjectId(document_id)})

            if document:
                # Convert ObjectId to string for JSON serialization
                document['_id'] = str(document['_id'])
                return document

            return None

        except Exception as e:
            logger.error(f"Failed to retrieve document: {e}")
            return None

    async def get_scraped_data_by_url(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve most recent scraped data for a URL

        Args:
            url: The URL to search for

        Returns:
            Most recent document for the URL or None
        """
        try:
            document = await self.collection.find_one(
                {"url": url},
                sort=[("scraped_at", -1)]  # Most recent first
            )

            if document:
                document['_id'] = str(document['_id'])
                return document

            return None

        except Exception as e:
            logger.error(f"Failed to retrieve document by URL: {e}")
            return None

    async def get_all_scraped_data(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Retrieve all scraped data with limit

        Args:
            limit: Maximum number of documents to return

        Returns:
            List of documents
        """
        try:
            cursor = self.collection.find().sort("scraped_at", -1).limit(limit)
            documents = await cursor.to_list(length=limit)

            # Convert ObjectIds to strings
            for doc in documents:
                doc['_id'] = str(doc['_id'])

            return documents

        except Exception as e:
            logger.error(f"Failed to retrieve documents: {e}")
            return []

    async def delete_scraped_data(self, document_id: str) -> bool:
        """
        Delete scraped data by ID

        Args:
            document_id: MongoDB document ID

        Returns:
            True if deleted, False otherwise
        """
        try:
            if not ObjectId.is_valid(document_id):
                return False

            result = await self.collection.delete_one({"_id": ObjectId(document_id)})

            if result.deleted_count > 0:
                logger.info(f"Deleted document: {document_id}")
                return True

            return False

        except Exception as e:
            logger.error(f"Failed to delete document: {e}")
            return False

    async def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about the collection"""
        try:
            count = await self.collection.count_documents({})

            # Get most recent scrape
            recent = await self.collection.find_one(sort=[("scraped_at", -1)])

            stats = {
                "total_documents": count,
                "collection_name": self.collection.name,
                "most_recent_scrape": recent.get("scraped_at") if recent else None
            }

            return stats

        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {}
