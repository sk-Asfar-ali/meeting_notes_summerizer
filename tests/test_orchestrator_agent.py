"""Tests for small helper behavior inside the orchestrator agent."""

from app.agents.orchestrator_agent import (
    format_action_items_response,
    is_action_items_question,
)


def test_is_action_items_question():
    """Action-item intent detection should catch common phrasings."""
    assert is_action_items_question("tell me about action items")
    assert is_action_items_question("what are the follow-up tasks?")
    assert not is_action_items_question("summarize the discussion")


def test_format_action_items_response_uses_saved_items():
    """Saved action items should be formatted into a readable chat reply."""
    response = format_action_items_response(
        [
            {
                "task": "Review the moratorium process",
                "owner": "Speaker 3",
                "deadline": "None",
                "status": "Pending",
            }
        ]
    )

    assert "Review the moratorium process" in response
    assert "Owner: Speaker 3" in response
    assert "Deadline: None" in response


def test_format_action_items_response_handles_empty_items():
    """The chat shortcut should give a friendly empty-state answer."""
    assert format_action_items_response([]) == "No action items were extracted for this meeting."
