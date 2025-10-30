from pydantic import BaseModel, HttpUrl, Field
from typing import Optional, Dict, Any
from datetime import datetime
from bson import ObjectId


class PyObjectId(ObjectId):
    """Custom ObjectId type for Pydantic"""

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)

    @classmethod
    def __get_pydantic_json_schema__(cls, field_schema):
        field_schema.update(type="string")


class ScrapeRequest(BaseModel):
    """Request model for scraping endpoint"""
    url: HttpUrl = Field(..., description="URL to scrape")

    class Config:
        json_schema_extra = {
            "example": {
                "url": "https://www.comune.codroipo.ud.it/it/servizi-224003/aire-iscrizione-italiani-residenti-allestero-241615"
            }
        }


class ScrapeResponse(BaseModel):
    """Response model for successful scrape"""
    id: str = Field(..., alias="_id", description="MongoDB document ID")
    url: str = Field(..., description="Scraped URL")
    title: Optional[str] = Field(None, description="Page title")
    status_code: int = Field(..., description="HTTP status code")
    scraped_at: datetime = Field(..., description="Timestamp of scrape")
    content_length: int = Field(..., description="Length of HTML content")
    success: bool = Field(True, description="Scrape success status")

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "_id": "507f1f77bcf86cd799439011",
                "url": "https://example.com",
                "title": "Example Page",
                "status_code": 200,
                "scraped_at": "2025-10-28T10:30:00",
                "content_length": 15420,
                "success": True
            }
        }


class ErrorResponse(BaseModel):
    """Response model for errors"""
    success: bool = Field(False, description="Scrape success status")
    error: str = Field(..., description="Error message")
    url: Optional[str] = Field(None, description="URL that failed")

    class Config:
        json_schema_extra = {
            "example": {
                "success": False,
                "error": "Failed to connect to URL",
                "url": "https://example.com"
            }
        }


class ScrapedDocument(BaseModel):
    """MongoDB document model for scraped data"""
    url: str
    html_content: str
    title: Optional[str] = None
    status_code: int
    scraped_at: datetime = Field(default_factory=datetime.utcnow)
    content_length: int
    headers: Optional[Dict[str, Any]] = None
    meta_description: Optional[str] = None
    kb_content: Optional[str] = None  # Formatted content for AI knowledge base

    success: bool = True
    error_message: Optional[str] = None