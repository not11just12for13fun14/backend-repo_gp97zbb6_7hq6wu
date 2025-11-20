"""
Database Schemas for Kokum & Coast

Each Pydantic model corresponds to a MongoDB collection (lowercased class name).
Use these models for validation before inserting/updating documents.
"""
from typing import List, Optional
from pydantic import BaseModel, Field, EmailStr


class MenuItem(BaseModel):
    name: str = Field(..., description="Dish name")
    category: str = Field(..., description="Category like Starters, Mains, Breads, Beverages, Desserts")
    description: Optional[str] = Field(None, description="Short description of the dish")
    price: float = Field(..., ge=0, description="Price in INR")
    veg: bool = Field(False, description="Vegetarian flag")
    spicy_level: Optional[int] = Field(None, ge=0, le=5, description="Spice level 0-5")
    image: Optional[str] = Field(None, description="Image URL")
    tags: List[str] = Field(default_factory=list, description="Search/filter tags")


class Reservation(BaseModel):
    name: str
    phone: str
    email: Optional[EmailStr] = None
    date: str = Field(..., description="YYYY-MM-DD")
    time: str = Field(..., description="HH:MM")
    guests: int = Field(..., ge=1, le=20)
    special_requests: Optional[str] = None
    status: str = Field("pending", description="pending | confirmed | cancelled")


class OrderItem(BaseModel):
    menu_item_id: Optional[str] = Field(None, description="MongoDB ObjectId string of the menu item")
    name: str
    qty: int = Field(..., ge=1)
    price: float = Field(..., ge=0)


class Order(BaseModel):
    items: List[OrderItem]
    subtotal: float = Field(..., ge=0)
    taxes: float = Field(..., ge=0)
    total: float = Field(..., ge=0)
    customer_name: str
    customer_phone: str
    customer_email: Optional[EmailStr] = None
    address: Optional[str] = None
    notes: Optional[str] = None
    status: str = Field("received", description="received | preparing | ready | completed | cancelled")
    payment_status: str = Field("pending", description="pending | paid | refunded")


class Review(BaseModel):
    name: str
    rating: int = Field(..., ge=1, le=5)
    comment: str
    city: Optional[str] = None


class AdminUser(BaseModel):
    email: EmailStr
    password_hash: str
    role: str = Field("admin")
