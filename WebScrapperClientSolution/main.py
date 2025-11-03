from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
from app.config.database import connect_to_mongo, close_mongo_connection
from app.routes import scrape_router, calendar_router
from app.services import DatabaseService
from app.config.database import get_database
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('app.log')
    ]
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events
    """
    # Startup
    logger.info("Starting FastAPI Web Scraper Service...")

    try:
        # Connect to MongoDB
        await connect_to_mongo()

        # Create database indexes
        db = get_database()
        db_service = DatabaseService(db)
        await db_service.create_indexes()

        # Start the reminder scheduler
        from app.services import reminder_service, background_monitor
        reminder_service.start()

        # Start the automated background monitor
        await background_monitor.start(db)

        # Start the event monitor for new calendar events
        from app.services import event_monitor
        await event_monitor.start()

    except Exception as e:
        logger.error(f"Startup failed: {e}")
        raise

    yield

    # Shutdown
    logger.info("Shutting down FastAPI Web Scraper Service...")

    # Stop background monitor
    from app.services import background_monitor, reminder_service, event_monitor
    await background_monitor.stop()

    # Stop event monitor
    await event_monitor.stop()

    # Stop the reminder scheduler
    reminder_service.shutdown()

    await close_mongo_connection()
    logger.info("Application shutdown complete")


# Create FastAPI application
app = FastAPI(
    title=os.getenv("APP_NAME", "FastAPI Web Scraper"),
    description="A web scraping service that accepts URLs, scrapes HTML content, and stores it in MongoDB",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS (Cross-Origin Resource Sharing)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(scrape_router)
app.include_router(calendar_router)


@app.get("/", tags=["root"])
async def root():
    """Root endpoint - API health check"""
    return {
        "message": "FastAPI Web Scraper Service",
        "status": "running",
        "docs": "/docs",
        "redoc": "/redoc"
    }


@app.get("/health", tags=["health"])
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "FastAPI Web Scraper"
    }


if __name__ == "__main__":
    import uvicorn

    # Run the application
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Auto-reload on code changes (development only)
        log_level="info"
    )
