"""Normalize raw model action items into the app's storage format."""

import uuid

def process_extracted_actions(meeting_id: str, raw_action_items: list) -> list[dict]:
    """Processes raw action items extracted by the LLM into a standardized schema."""
    processed = []
    for item in raw_action_items:
        processed.append({
            "id": str(uuid.uuid4()),
            "meeting_id": meeting_id,
            "task": item.get('task', 'Unknown task'),
            "owner": item.get('owner', 'Unassigned'),
            "deadline": item.get('deadline', 'None'),
            "status": "Pending"
        })
    return processed
