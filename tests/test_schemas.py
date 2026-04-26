"""Basic schema smoke tests."""

from app.schemas.meeting import Meeting
from app.schemas.action_item import ActionItem

def test_meeting_schema():
    """Meeting defaults should be populated when only transcript text is given."""
    m = Meeting(transcript="Test transcript")
    assert m.title == "Untitled Meeting"
    assert m.transcript == "Test transcript"
    assert m.id is not None

def test_action_item_schema():
    """Action item defaults should match the UI/storage assumptions."""
    a = ActionItem(id="123", meeting_id="m123", task="Test task")
    assert a.owner == "Unassigned"
    assert a.status == "Pending"
