from app.schemas.meeting import Meeting
from app.schemas.action_item import ActionItem

def test_meeting_schema():
    m = Meeting(transcript="Test transcript")
    assert m.title == "Untitled Meeting"
    assert m.transcript == "Test transcript"
    assert m.id is not None

def test_action_item_schema():
    a = ActionItem(id="123", meeting_id="m123", task="Test task")
    assert a.owner == "Unassigned"
    assert a.status == "Pending"
