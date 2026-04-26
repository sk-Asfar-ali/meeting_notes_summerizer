"""Tests for dataset shape detection and transcript reconstruction."""

import pandas as pd

from app.services.dataset_loader import (
    DATASET_MODE_COMBINE_ALL,
    DATASET_MODE_SINGLE_ROW,
    DatasetLoader,
)


def test_get_random_sample_combines_rows_by_meeting_id(monkeypatch):
    """Rows sharing a meeting id should become one transcript."""
    df = pd.DataFrame(
        [
            {"Meeting_UID": "m1", "Transcript": "Alice: First item"},
            {"Meeting_UID": "m1", "Transcript": "Bob: Second item"},
            {"Meeting_UID": "m2", "Transcript": "Priya: Other meeting"},
        ]
    )
    monkeypatch.setattr("app.services.dataset_loader.random.choice", lambda values: "m1")

    sample = DatasetLoader().get_random_sample(df)

    assert sample["title"] == "Meeting m1 (2 dataset rows combined)"
    assert "Alice: First item" in sample["transcript"]
    assert "Bob: Second item" in sample["transcript"]
    assert sample["metadata"]["dataset_mode"] == "grouped_rows"
    assert sample["metadata"]["rows_combined"] == 2


def test_get_random_sample_handles_one_transcript_per_row(monkeypatch):
    """Single-row transcript datasets should preserve the chosen row."""
    df = pd.DataFrame(
        [
            {"Transcript": "Full meeting one"},
            {"Transcript": "Full meeting two"},
        ]
    )
    monkeypatch.setattr("app.services.dataset_loader.random.randint", lambda start, end: 1)

    sample = DatasetLoader().get_random_sample(df)

    assert sample["title"] == "Random sample: Transcript row 1 of 2"
    assert sample["transcript"] == "Full meeting two"
    assert sample["metadata"]["dataset_mode"] == "single_row"


def test_get_random_sample_adds_speaker_to_turn_rows(monkeypatch):
    """Speaker columns should be rendered into "Speaker: text" transcript lines."""
    df = pd.DataFrame(
        [
            {"meeting_id": "m1", "speaker": "Alice", "utterance": "We should launch."},
            {"meeting_id": "m1", "speaker": "Bob", "utterance": "I will test it."},
        ]
    )
    monkeypatch.setattr("app.services.dataset_loader.random.choice", lambda values: "m1")

    sample = DatasetLoader().get_random_sample(df)

    assert "Alice: We should launch." in sample["transcript"]
    assert "Bob: I will test it." in sample["transcript"]


def test_get_random_sample_combines_ungrouped_turn_rows():
    """Turn-style datasets without meeting ids should still combine into one meeting."""
    df = pd.DataFrame(
        [
            {"turn": 2, "speaker": "Bob", "utterance": "I will test it."},
            {"turn": 1, "speaker": "Alice", "utterance": "We should launch."},
            {"turn": 3, "speaker": "Alice", "utterance": "Deadline is Friday."},
        ]
    )

    sample = DatasetLoader().get_random_sample(df)

    assert sample["metadata"]["dataset_mode"] == "ungrouped_rows_combined"
    assert sample["metadata"]["rows_combined"] == 3
    assert sample["transcript"].startswith("Alice: We should launch.")
    assert "Bob: I will test it." in sample["transcript"]
    assert "Alice: Deadline is Friday." in sample["transcript"]


def test_get_random_sample_keeps_full_transcript_rows_separate(monkeypatch):
    """Long row-level transcripts should not be mistaken for turn-by-turn data."""
    df = pd.DataFrame(
        [
            {"speaker": "Alice", "Transcript": "Full meeting one " * 80},
            {"speaker": "Bob", "Transcript": "Full meeting two " * 80},
            {"speaker": "Priya", "Transcript": "Full meeting three " * 80},
        ]
    )
    monkeypatch.setattr("app.services.dataset_loader.random.randint", lambda start, end: 2)

    sample = DatasetLoader().get_random_sample(df)

    assert sample["metadata"]["dataset_mode"] == "single_row"
    assert "Full meeting three" in sample["transcript"]


def test_get_random_sample_parses_json_turns_in_single_cell(monkeypatch):
    """Structured JSON stored inside one cell should be converted into plain transcript text."""
    df = pd.DataFrame(
        [
            {
                "title": "Planning call",
                "dialogue": '[{"speaker": "Alice", "text": "We need a beta."}, {"speaker": "Bob", "text": "I will draft the plan."}]',
            }
        ]
    )
    monkeypatch.setattr("app.services.dataset_loader.random.randint", lambda start, end: 0)

    sample = DatasetLoader().get_random_sample(df)

    assert sample["title"] == "Planning call"
    assert "Alice: We need a beta." in sample["transcript"]
    assert "Bob: I will draft the plan." in sample["transcript"]


def test_get_random_sample_falls_back_to_best_text_column(monkeypatch):
    """The loader should still work when the text column has a less obvious name."""
    df = pd.DataFrame(
        [
            {"id": "m1", "notes": "Alice discussed roadmap risks and Bob accepted the testing task."},
            {"id": "m2", "notes": "Priya reviewed hiring blockers and Omar took the reporting action."},
        ]
    )
    monkeypatch.setattr("app.services.dataset_loader.random.randint", lambda start, end: 1)

    sample = DatasetLoader().get_random_sample(df)

    assert sample["metadata"]["text_column"] == "notes"
    assert sample["transcript"] == "Priya reviewed hiring blockers and Omar took the reporting action."


def test_get_random_sample_skips_empty_selected_row(monkeypatch):
    """Empty chosen rows should fall back to the first usable transcript row."""
    df = pd.DataFrame(
        [
            {"Transcript": ""},
            {"Transcript": "A complete meeting transcript is here."},
        ]
    )
    monkeypatch.setattr("app.services.dataset_loader.random.randint", lambda start, end: 0)

    sample = DatasetLoader().get_random_sample(df)

    assert sample["transcript"] == "A complete meeting transcript is here."
    assert sample["metadata"]["selected_row"] == 1


def test_get_dataset_profile_reports_detected_columns():
    """The dataset profile should explain the detected structure to the UI."""
    df = pd.DataFrame(
        [
            {"meeting_id": "m1", "speaker": "Alice", "utterance": "First"},
            {"meeting_id": "m1", "speaker": "Bob", "utterance": "Second"},
        ]
    )

    profile = DatasetLoader().get_dataset_profile(df)

    assert profile["row_count"] == 2
    assert profile["text_column"] == "utterance"
    assert profile["group_column"] == "meeting_id"
    assert profile["speaker_column"] == "speaker"
    assert profile["detected_mode"] == "grouped_rows"


def test_get_random_sample_can_force_combine_all_rows():
    """Explicit combine-all mode should ignore auto-detection and merge every row."""
    df = pd.DataFrame(
        [
            {"Transcript": "Full transcript one."},
            {"Transcript": "Full transcript two."},
        ]
    )

    sample = DatasetLoader().get_random_sample(df, mode=DATASET_MODE_COMBINE_ALL)

    assert sample["metadata"]["dataset_mode"] == "combine_all_rows"
    assert "Full transcript one." in sample["transcript"]
    assert "Full transcript two." in sample["transcript"]


def test_get_random_sample_can_force_single_row(monkeypatch):
    """Explicit single-row mode should still work on turn-style datasets."""
    df = pd.DataFrame(
        [
            {"speaker": "Alice", "utterance": "First turn"},
            {"speaker": "Bob", "utterance": "Second turn"},
            {"speaker": "Priya", "utterance": "Third turn"},
        ]
    )
    monkeypatch.setattr("app.services.dataset_loader.random.randint", lambda start, end: 1)

    sample = DatasetLoader().get_random_sample(df, mode=DATASET_MODE_SINGLE_ROW)

    assert sample["metadata"]["dataset_mode"] == "single_row"
    assert sample["transcript"] == "Bob: Second turn"
