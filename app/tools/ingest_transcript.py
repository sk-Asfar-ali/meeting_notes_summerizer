import uuid
from datetime import datetime

def ingest_raw_transcript(raw_text: str, title: str = "Untitled Meeting", metadata: dict = None) -> dict:
    """Creates a meeting record from raw transcript text."""
    return {
        "id": str(uuid.uuid4()),
        "title": title,
        "date": datetime.now().isoformat(),
        "transcript": raw_text,
        "metadata": metadata or {}
    }
