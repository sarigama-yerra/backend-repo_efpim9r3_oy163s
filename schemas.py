"""
Database Schemas for ViralQuoteMachine

Each Pydantic model represents a MongoDB collection.
Collection name is the lowercase class name.
"""
from pydantic import BaseModel, Field, HttpUrl, EmailStr
from typing import Optional, List, Literal
from datetime import datetime

QuoteCategory = Literal["motivational", "love", "business", "fitness", "funny"]

class Quote(BaseModel):
    text: str = Field(..., description="Quote content")
    category: QuoteCategory = Field(..., description="Quote category")
    author: Optional[str] = Field(None, description="Author if applicable")
    image_url: Optional[HttpUrl] = Field(None, description="Hosted image URL")
    width: Optional[int] = Field(None)
    height: Optional[int] = Field(None)
    watermark: bool = Field(True, description="Whether image contains watermark")
    quality: Literal["standard", "high"] = Field("standard")
    affiliate_links: List[HttpUrl] = Field(default_factory=list, description="Amazon affiliate links")
    likes: int = Field(0)
    views: int = Field(0)
    posted: bool = Field(False, description="Posted to social platforms")
    platforms: List[str] = Field(default_factory=list, description="Where posted")
    seo_title: Optional[str] = None
    seo_description: Optional[str] = None

class Subscriber(BaseModel):
    email: EmailStr
    created_from: Literal["web", "import", "api"] = "web"
    active: bool = True

class User(BaseModel):
    email: EmailStr
    name: Optional[str] = None
    is_premium: bool = False
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None

class GenerationJob(BaseModel):
    triggered_by: Literal["cron", "manual", "web"] = "cron"
    status: Literal["pending", "running", "completed", "failed"] = "pending"
    total_quotes: int = 0
    error: Optional[str] = None

class Click(BaseModel):
    quote_id: str
    url: HttpUrl
    at: datetime = Field(default_factory=datetime.utcnow)
