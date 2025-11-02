from fastapi import APIRouter, HTTPException, status, Depends
from app.models import ScrapeRequest, ScrapeResponse, ErrorResponse
from app.services import scraper_service, DatabaseService
from app.config.database import get_database
import logging

from app.services.kb_formatter import kb_formatter_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/scrape",
    tags=["scraping"]
)


def get_db_service():
    """Dependency to get database service"""
    db = get_database()
    return DatabaseService(db)


@router.post(
    "/",
    response_model=ScrapeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Scrape a URL",
    description="Scrape HTML content from the provided URL and store it in MongoDB",
    responses={
        201: {
            "description": "Successfully scraped and stored",
            "model": ScrapeResponse
        },
        400: {
            "description": "Invalid URL or request",
            "model": ErrorResponse
        },
        500: {
            "description": "Server error during scraping",
            "model": ErrorResponse
        }
    }
)
async def scrape_url(
        request: ScrapeRequest,
        db_service: DatabaseService = Depends(get_db_service)
):
    """
    Scrape a URL, format its content for a knowledge base,
    and store everything in MongoDB

    - **url**: Valid HTTP/HTTPS URL to scrape

    Returns the scraped data information including MongoDB document ID
    """
    try:
        logger.info(f"Received scrape request for: {request.url}")

        # 1. Scrape the URL
        scraped_data = await scraper_service.scrape_url(str(request.url))

        # 2. --- NEW: Format content for Knowledge Base ---
        if scraped_data.get('html_content'):
            logger.info(f"Formatting content for KB...")
            kb_content = kb_formatter_service.format(scraped_data['html_content'])
            scraped_data['kb_content'] = kb_content
            # We can now clear the raw HTML if we don't want to store it
            # del scraped_data['html_content']
            # Or keep it, which is useful for debugging (as we do here)
        else:
            logger.warning("No html_content found to format.")
            scraped_data['kb_content'] = None
        # --------------------------------------------------

        # 3. Save to MongoDB (now includes 'kb_content')
        document_id = await db_service.save_scraped_data(scraped_data)

        # 4. Prepare response
        response = ScrapeResponse(
            _id=document_id,
            url=scraped_data['url'],
            title=scraped_data.get('title'),
            status_code=scraped_data['status_code'],
            scraped_at=scraped_data['scraped_at'],
            content_length=scraped_data['content_length'],
            success=True
        )

        logger.info(f"Successfully completed scrape request for: {request.url}")

        return response

    except Exception as e:
        # ... (error handling) ...
        # (No changes needed in the error handling block)
        error_message = str(e)
        logger.error(f"Scrape failed for {request.url}: {error_message}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": error_message,
                "url": str(request.url)
            }
        )


@router.get(
    "/{document_id}",
    summary="Get scraped data by ID",
    description="Retrieve scraped data from MongoDB by document ID"
)
async def get_scraped_data(
        document_id: str,
        db_service: DatabaseService = Depends(get_db_service)
):
    """
    Retrieve scraped data by MongoDB document ID

    - **document_id**: MongoDB document ID
    """
    try:
        document = await db_service.get_scraped_data_by_id(document_id)

        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document with ID {document_id} not found"
            )

        return document

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve document: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get(
    "/",
    summary="Get all scraped data",
    description="Retrieve all scraped data with optional limit"
)
async def get_all_scraped_data(
        limit: int = 50,
        db_service: DatabaseService = Depends(get_db_service)
):
    """
    Retrieve all scraped data

    - **limit**: Maximum number of documents to return (default: 50, max: 100)
    """
    try:
        if limit > 100:
            limit = 100

        documents = await db_service.get_all_scraped_data(limit=limit)

        return {
            "total": len(documents),
            "limit": limit,
            "data": documents
        }

    except Exception as e:
        logger.error(f"Failed to retrieve documents: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get(
    "/stats/collection",
    summary="Get collection statistics",
    description="Get statistics about the scraped data collection"
)
async def get_collection_stats(
        db_service: DatabaseService = Depends(get_db_service)
):
    """Get statistics about the scraped data collection"""
    try:
        stats = await db_service.get_collection_stats()
        return stats
    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
