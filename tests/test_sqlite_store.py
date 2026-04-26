"""Tests for SQLite summary persistence behavior."""

from app.memory.sqlite_store import SQLiteStore


def test_save_summary_replaces_old_action_items(tmp_path):
    """Reprocessing a meeting should replace old action items instead of appending."""
    store = SQLiteStore(str(tmp_path / "meeting_notes.db"))
    meeting = {
        "id": "meeting-1",
        "title": "Planning",
        "date": "2026-04-25",
        "transcript": "Transcript",
        "metadata": {},
    }
    store.save_meeting(meeting)

    store.save_summary(
        {
            "meeting_id": "meeting-1",
            "executive_summary": "First",
            "action_items": [
                {
                    "id": "action-1",
                    "meeting_id": "meeting-1",
                    "task": "Old task",
                    "owner": "Alice",
                    "deadline": "Friday",
                    "status": "Pending",
                }
            ],
        }
    )
    store.save_summary(
        {
            "meeting_id": "meeting-1",
            "executive_summary": "Second",
            "action_items": [],
        }
    )

    summary = store.get_summary("meeting-1")

    assert summary["executive_summary"] == "Second"
    assert summary["action_items"] == []
