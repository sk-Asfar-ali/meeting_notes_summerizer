"""Tests for uploaded file transcript extraction."""

from io import BytesIO

import pytest

from app.services.transcript_file_loader import (
    TranscriptFileError,
    extract_uploaded_transcript,
)


class NamedBytesIO(BytesIO):
    """Simple upload-like object with a stable filename for tests."""

    def __init__(self, content: bytes, name: str):
        super().__init__(content)
        self.name = name


def test_extract_uploaded_transcript_from_text_file():
    """Plain text uploads should be decoded directly."""
    uploaded = NamedBytesIO(b"Alice: We decided to launch.\nBob: I will test it.", "meeting.txt")

    sample = extract_uploaded_transcript(uploaded)

    assert sample["title"] == "Uploaded file: meeting.txt"
    assert "Alice: We decided to launch." in sample["transcript"]
    assert sample["metadata"]["dataset_mode"] == "uploaded_text"
    assert sample["metadata"]["file_type"] == "txt"


def test_extract_uploaded_transcript_from_csv_combines_rows():
    """CSV uploads should be converted into one transcript sample."""
    uploaded = NamedBytesIO(
        b"speaker,utterance\nAlice,We should launch.\nBob,I will test it.",
        "meeting.csv",
    )

    sample = extract_uploaded_transcript(uploaded)

    assert sample["metadata"]["dataset_mode"] == "uploaded_tabular"
    assert sample["metadata"]["rows_combined"] == 2
    assert "Alice: We should launch." in sample["transcript"]
    assert "Bob: I will test it." in sample["transcript"]


def test_extract_uploaded_transcript_rejects_unsupported_file_type():
    """Unsupported file extensions should raise a friendly error."""
    uploaded = NamedBytesIO(b"hello", "meeting.zip")

    with pytest.raises(TranscriptFileError, match="Unsupported file type"):
        extract_uploaded_transcript(uploaded)


def test_extract_uploaded_transcript_rejects_empty_file():
    """Empty uploads should be rejected before further processing."""
    uploaded = NamedBytesIO(b"", "meeting.txt")

    with pytest.raises(TranscriptFileError, match="empty"):
        extract_uploaded_transcript(uploaded)
