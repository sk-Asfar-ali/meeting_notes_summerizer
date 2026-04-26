"""Basic text cleanup before a transcript goes into the pipeline."""

import re

def clean_transcript(text: str) -> str:
    """Removes excessive whitespace and weird characters from transcript."""
    if not text:
        return ""
    # Normalize repeated whitespace without disturbing the transcript order.
    text = re.sub(r'\n+', '\n', text)
    text = re.sub(r'[ \t]{2,}', ' ', text)
    text = re.sub(r'[ \t]+\n', '\n', text)
    # Drop unusual unicode characters to keep downstream parsing predictable.
    text = text.encode('ascii', 'ignore').decode()
    return text.strip()
