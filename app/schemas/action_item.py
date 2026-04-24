from pydantic import BaseModel, Field
from typing import Optional

class ActionItem(BaseModel):
    id: str
    meeting_id: str
    task: str
    owner: Optional[str] = "Unassigned"
    deadline: Optional[str] = "None"
    status: str = "Pending"
