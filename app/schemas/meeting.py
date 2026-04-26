"""Pydantic schema for a stored meeting record."""

from pydantic import BaseModel, Field
from datetime import datetime
import uuid

class Meeting(BaseModel):
    """Validated meeting record used when a transcript enters the system."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str = "Untitled Meeting"
    date: datetime = Field(default_factory=datetime.now)
    transcript: str
    metadata: dict = Field(default_factory=dict)
