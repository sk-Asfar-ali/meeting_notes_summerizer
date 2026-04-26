"""Tests for small transcript-processing helpers."""

import json

from app.tools.clean_text import clean_transcript
from app.tools.chunk_text import chunk_transcript
from app.tools.compact_transcript import compact_transcript_for_llm
from app.tools.extract_actions import process_extracted_actions
from app.tools.summarize_meeting import parse_summary_response, summarize_and_extract


class FakeLLMClient:
    """Minimal fake LLM client for testing multi-step summarization flows."""

    def __init__(self, responses):
        self.responses = responses
        self.prompts = []

    def generate(self, prompt: str, system_prompt=None, json_format=False, temperature=0.3):
        self.prompts.append(prompt)
        return self.responses[len(self.prompts) - 1]

def test_clean_transcript():
    """Whitespace cleanup should preserve the transcript content itself."""
    raw_text = "This   is \n\n a test\n."
    cleaned = clean_transcript(raw_text)
    assert cleaned == "This is\n a test\n."

def test_chunk_transcript():
    """Chunking should split long text while keeping chunk size under control."""
    text = " ".join(["word"] * 100)
    chunks = chunk_transcript(text, max_words=60, overlap=10)
    assert len(chunks) == 2
    assert len(chunks[0].split()) == 60

def test_compact_transcript_keeps_short_text_unchanged():
    """Short transcripts should not be altered by the compaction helper."""
    transcript = "Alice: We decided to ship today."
    assert compact_transcript_for_llm(transcript, max_chars=4000) == transcript

def test_compact_transcript_limits_long_text_and_keeps_important_lines():
    """Compaction should keep likely decision/action lines from the middle."""
    transcript = "\n".join(
        ["Intro line"] * 200
        + ["Priya: Decision is to launch Monday.", "Omar: Action item is to update the docs."]
        + ["Wrap up"] * 200
    )
    compacted = compact_transcript_for_llm(transcript, max_chars=4000)
    assert len(compacted) <= 4000
    assert "Decision is to launch Monday" in compacted
    assert "Action item is to update the docs" in compacted

def test_process_extracted_actions():
    """Raw model action items should be normalized into the storage format."""
    raw_actions = [
        {"task": "Do X", "owner": "Alice", "deadline": "Tomorrow"}
    ]
    processed = process_extracted_actions("meeting_123", raw_actions)
    assert len(processed) == 1
    assert processed[0]['meeting_id'] == "meeting_123"
    assert processed[0]['task'] == "Do X"
    assert processed[0]['owner'] == "Alice"
    assert processed[0]['status'] == "Pending"
    assert 'id' in processed[0]


def test_parse_summary_response_handles_markdown_fenced_json():
    """Summary parsing should tolerate fenced JSON returned by the model."""
    response = """```json
{
  "executive_summary": "Planning update.",
  "bullet_highlights": "Launch moved to Friday.",
  "decisions": ["Ship the beta"],
  "risks_blockers": null,
  "action_items": [{"task": "Update docs", "owner": "Alice", "deadline": "Friday"}]
}
```"""

    parsed = parse_summary_response(response)

    assert parsed["executive_summary"] == "Planning update."
    assert parsed["bullet_highlights"] == ["Launch moved to Friday."]
    assert parsed["decisions"] == ["Ship the beta"]
    assert parsed["risks_blockers"] == []
    assert parsed["action_items"][0]["task"] == "Update docs"


def test_parse_summary_response_extracts_json_from_extra_text():
    """Summary parsing should recover JSON even when extra prose is present."""
    response = 'Here is the JSON: {"executive_summary": "Done", "action_items": []} Thanks.'

    parsed = parse_summary_response(response)

    assert parsed["executive_summary"] == "Done"
    assert parsed["bullet_highlights"] == []


def test_summarize_and_extract_merges_chunk_summaries(monkeypatch):
    """Long transcripts should be summarized chunk by chunk and then merged."""
    monkeypatch.setattr("app.tools.summarize_meeting.get_llm_transcript_char_limit", lambda: 300)

    transcript = (
        ("Intro text. " * 14)
        + "\nBob: Decision is to launch on Friday.\n"
        + ("Middle text. " * 8)
        + "\nPriya: Action item is to update the docs by Friday.\n"
        + ("Tail text. " * 8)
    )
    responses = [
        json.dumps(
            {
                "executive_summary": "Chunk one summary.",
                "bullet_highlights": ["Launch date discussed."],
                "decisions": ["Launch on Friday"],
                "risks_blockers": [],
                "action_items": [],
            }
        ),
        json.dumps(
            {
                "executive_summary": "Chunk two summary.",
                "bullet_highlights": ["Documentation follow-up."],
                "decisions": [],
                "risks_blockers": ["Docs are behind schedule."],
                "action_items": [
                    {"task": "Update the docs", "owner": "Priya", "deadline": "Friday"}
                ],
            }
        ),
        json.dumps(
            {
                "executive_summary": "Merged whole-meeting summary.",
                "bullet_highlights": ["Launch date discussed.", "Documentation follow-up."],
                "decisions": ["Launch on Friday"],
                "risks_blockers": ["Docs are behind schedule."],
                "action_items": [
                    {"task": "Update the docs", "owner": "Priya", "deadline": "Friday"}
                ],
            }
        ),
    ]
    llm_client = FakeLLMClient(responses)

    summary = summarize_and_extract(transcript, llm_client)

    assert summary["executive_summary"] == "Merged whole-meeting summary."
    assert summary["decisions"] == ["Launch on Friday"]
    assert summary["risks_blockers"] == ["Docs are behind schedule."]
    assert summary["action_items"][0]["task"] == "Update the docs"
    assert len(llm_client.prompts) == 3


def test_summarize_and_extract_falls_back_to_deterministic_merge(monkeypatch):
    """If the merge call fails, decisions and action items should still survive."""
    monkeypatch.setattr("app.tools.summarize_meeting.get_llm_transcript_char_limit", lambda: 300)

    transcript = (
        ("Intro text. " * 14)
        + "\nAlice: Decision is to freeze scope.\n"
        + ("Middle text. " * 8)
        + "\nBob: Action item is to test the API by Monday.\n"
        + ("Tail text. " * 8)
    )
    responses = [
        json.dumps(
            {
                "executive_summary": "Chunk one.",
                "bullet_highlights": ["Scope discussion."],
                "decisions": ["Freeze scope"],
                "risks_blockers": [],
                "action_items": [],
            }
        ),
        json.dumps(
            {
                "executive_summary": "Chunk two.",
                "bullet_highlights": ["Testing follow-up."],
                "decisions": [],
                "risks_blockers": ["Testing time is tight."],
                "action_items": [
                    {"task": "Test the API", "owner": "Bob", "deadline": "Monday"}
                ],
            }
        ),
        "not valid json",
    ]
    llm_client = FakeLLMClient(responses)

    summary = summarize_and_extract(transcript, llm_client)

    assert "Freeze scope" in summary["decisions"]
    assert "Testing time is tight." in summary["risks_blockers"]
    assert summary["action_items"][0]["task"] == "Test the API"
