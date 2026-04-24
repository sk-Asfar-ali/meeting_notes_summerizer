from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
import uuid

class Meeting(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str = "Untitled Meeting"
    date: datetime = Field(default_factory=datetime.now)
    transcript: str
    metadata: dict = Field(default_factory=dict)
