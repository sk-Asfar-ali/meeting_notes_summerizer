"""Pydantic schema for one extracted action item."""

from pydantic import BaseModel
from typing import Optional

class ActionItem(BaseModel):
    """Validated shape for an action item shown in the UI and stored in SQLite."""

    id: str
    meeting_id: str
    task: str
    owner: Optional[str] = "Unassigned"
    deadline: Optional[str] = "None"
    status: str = "Pending"
