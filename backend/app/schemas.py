from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field

EMAIL_RE = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
ROLE_RE = r"^(admin|analyst|viewer)$"
DEVICES = ("mobile", "desktop", "tablet")
SECTIONS = ("overview", "funnel", "daily", "devices")


class RegisterIn(BaseModel):
    email: str = Field(pattern=EMAIL_RE, max_length=120)
    password: str = Field(min_length=6, max_length=100)
    full_name: str = Field(min_length=1, max_length=100)


class LoginIn(BaseModel):
    email: str
    password: str


class UserCreate(RegisterIn):
    role: str = Field(default="viewer", pattern=ROLE_RE)


class UserPatch(BaseModel):
    role: Optional[str] = Field(default=None, pattern=ROLE_RE)
    is_active: Optional[bool] = None


class EventIn(BaseModel):
    visitor_id: str = Field(min_length=1, max_length=64)
    session_id: Optional[str] = Field(default=None, max_length=64)
    event_type: str = Field(pattern="^(page_view|view_product|add_to_cart|purchase|click)$")
    page: str = "/"
    device: str = Field(default="desktop", pattern="^(mobile|desktop|tablet)$")
    properties: dict = {}
    created_at: Optional[datetime] = None


class GenerateIn(BaseModel):
    n_users: int = Field(ge=1, le=20_000)
    n_sessions: int = Field(ge=1, le=50_000)
    n_events: int = Field(ge=1, le=200_000)
    days: int = Field(default=14, ge=1, le=365)
    replace: bool = False


class SummaryIn(BaseModel):
    days: int = Field(default=14, ge=1, le=365)
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    devices: Optional[list[str]] = None
    sections: list[str] = list(SECTIONS)
    question: Optional[str] = Field(default=None, max_length=500)
