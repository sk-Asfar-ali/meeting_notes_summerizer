"""Pydantic schema for the structured summary returned by the LLM pipeline."""

from pydantic import BaseModel, Field
from typing import List
from app.schemas.action_item import ActionItem

class Summary(BaseModel):
    """Validated summary object combining prose output and action items."""

    meeting_id: str
    executive_summary: str
    bullet_highlights: List[str] = Field(default_factory=list)
    decisions: List[str] = Field(default_factory=list)
    risks_blockers: List[str] = Field(default_factory=list)
    action_items: List[ActionItem] = Field(default_factory=list)
