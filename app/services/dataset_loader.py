"""Dataset loading and transcript reconstruction helpers.

This module tries to recognize common dataset layouts and turn rows back into a
single meeting transcript the rest of the pipeline can understand.
"""

import pandas as pd
import os
import logging
import random
import ast
import json
from typing import Optional

logger = logging.getLogger(__name__)


SUPPORTED_DATASET_EXTENSIONS = (".csv", ".parquet", ".json", ".jsonl", ".ndjson")
SHORT_TURN_AVG_CHARS = 280
MIN_ROWS_FOR_UNGROUPED_TURN_TRANSCRIPT = 3
DATASET_MODE_AUTO = "auto"
DATASET_MODE_SINGLE_ROW = "single_row"
DATASET_MODE_GROUPED_ROWS = "grouped_rows"
DATASET_MODE_COMBINE_ALL = "combine_all_rows"
DATASET_MODE_UNGROUPED_COMBINED = "ungrouped_rows_combined"
DATASET_MODES = {
    DATASET_MODE_AUTO,
    DATASET_MODE_SINGLE_ROW,
    DATASET_MODE_GROUPED_ROWS,
    DATASET_MODE_COMBINE_ALL,
}

TEXT_COLUMN_KEYWORDS = (
    "transcript",
    "dialogue",
    "dialog",
    "utterance",
    "conversation",
    "message",
    "text",
    "content",
    "sentence",
    "body",
)

GROUP_COLUMN_KEYWORDS = (
    "meeting_uid",
    "meetinguid",
    "meeting_id",
    "meetingid",
    "meeting",
    "session_id",
    "conversation_id",
    "conversationid",
    "call_id",
    "video_id",
    "document_id",
    "file_id",
    "episode_id",
    "recording_id",
    "transcript_id",
)

SPEAKER_COLUMN_KEYWORDS = (
    "speaker",
    "speaker_name",
    "participant",
    "person",
    "role",
)

TITLE_COLUMN_KEYWORDS = (
    "title",
    "meeting_title",
    "meeting_name",
    "subject",
    "topic",
)

ORDER_COLUMN_KEYWORDS = (
    "timestamp",
    "start_time",
    "end_time",
    "start",
    "turn",
    "turn_id",
    "line",
    "line_number",
    "sequence",
    "seq",
    "order",
    "index",
)


def _normalize_column_name(column: object) -> str:
    """Normalize column names so heuristic matching is more forgiving."""
    return str(column).lower().strip().replace("-", "_").replace(" ", "_")


def _find_column(df: pd.DataFrame, keywords: tuple[str, ...]) -> Optional[str]:
    """Find the best matching column for a set of common dataset names."""
    normalized_columns = {_normalize_column_name(col): col for col in df.columns}

    for keyword in keywords:
        if keyword in normalized_columns:
            return normalized_columns[keyword]

    for col in df.columns:
        col_name = _normalize_column_name(col)
        if any(keyword in col_name for keyword in keywords):
            return col

    return None


def _is_missing_value(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and pd.isna(value):
        return True
    if isinstance(value, str):
        stripped = value.strip()
        return not stripped or stripped.lower() in {"nan", "none", "null"}
    return False


def _parse_structured_text(value: str) -> object:
    """Parse JSON-like transcript cells when a dataset stores turns in one field."""
    stripped = value.strip()
    if not stripped or stripped[0] not in "[{":
        return value

    for parser in (json.loads, ast.literal_eval):
        try:
            return parser(stripped)
        except (ValueError, SyntaxError, TypeError, json.JSONDecodeError):
            continue
    return value


def _find_key(mapping: dict, keywords: tuple[str, ...]) -> Optional[str]:
    normalized_keys = {_normalize_column_name(key): key for key in mapping.keys()}
    for keyword in keywords:
        if keyword in normalized_keys:
            return normalized_keys[keyword]

    for key in mapping.keys():
        key_name = _normalize_column_name(key)
        if any(keyword in key_name for keyword in keywords):
            return key
    return None


def _text_from_value(value: object) -> str:
    """Convert scalar, list, or dict-like transcript cells into plain text."""
    if _is_missing_value(value):
        return ""

    if isinstance(value, str):
        parsed = _parse_structured_text(value)
        if parsed is not value:
            return _text_from_value(parsed)
        return value.strip()

    if isinstance(value, dict):
        text_key = _find_key(value, TEXT_COLUMN_KEYWORDS)
        speaker_key = _find_key(value, SPEAKER_COLUMN_KEYWORDS)

        if text_key:
            text = _text_from_value(value.get(text_key))
            if not text:
                return ""
            if speaker_key:
                speaker = _text_from_value(value.get(speaker_key))
                if speaker and not text.lower().startswith(f"{speaker.lower()}:"):
                    return f"{speaker}: {text}"
            return text

        parts = [
            _text_from_value(item_value)
            for item_key, item_value in value.items()
            if _normalize_column_name(item_key) not in GROUP_COLUMN_KEYWORDS
        ]
        return "\n".join(part for part in parts if part)

    if isinstance(value, (list, tuple)):
        return "\n".join(part for part in (_text_from_value(item) for item in value) if part)

    if pd.isna(value):
        return ""
    return str(value).strip()


def _sample_nonempty_texts(df: pd.DataFrame, column: str, limit: int = 500) -> list[str]:
    texts = []
    for value in df[column].head(limit):
        text = _text_from_value(value)
        if text:
            texts.append(text)
    return texts


def _find_text_column(df: pd.DataFrame) -> Optional[str]:
    """Pick the most likely transcript/text column using names and content."""
    if df.empty:
        return None

    best_col = None
    best_score = float("-inf")

    for col in df.columns:
        col_name = _normalize_column_name(col)
        texts = _sample_nonempty_texts(df, col)
        if not texts:
            continue

        avg_len = sum(len(text) for text in texts) / len(texts)
        nonempty_ratio = len(texts) / max(1, min(len(df), 500))
        score = min(avg_len / 8, 80) + (nonempty_ratio * 30)

        for index, keyword in enumerate(TEXT_COLUMN_KEYWORDS):
            if col_name == keyword:
                score += 220 - index
                break
            if keyword in col_name:
                score += 120 - index
                break

        if any(keyword == col_name or keyword in col_name for keyword in GROUP_COLUMN_KEYWORDS):
            score -= 180
        if any(keyword == col_name or keyword in col_name for keyword in SPEAKER_COLUMN_KEYWORDS):
            score -= 140
        if any(keyword == col_name or keyword in col_name for keyword in ORDER_COLUMN_KEYWORDS):
            score -= 140

        if score > best_score:
            best_col = col
            best_score = score

    return best_col


def _find_group_column(df: pd.DataFrame, text_col: str) -> Optional[str]:
    """Find a grouping column when a meeting is split across multiple rows."""
    group_col = _find_column(df, GROUP_COLUMN_KEYWORDS)
    if group_col and group_col != text_col:
        return group_col
    return None


def _sort_rows_for_transcript(rows: pd.DataFrame) -> pd.DataFrame:
    order_col = _find_column(rows, ORDER_COLUMN_KEYWORDS)
    if order_col:
        return rows.sort_values(order_col, kind="stable")
    return rows


def _format_transcript_row(row: pd.Series, text_col: str, speaker_col: Optional[str]) -> str:
    text = _text_from_value(row.get(text_col, ""))
    if not text:
        return ""

    if not speaker_col:
        return text

    speaker = _text_from_value(row.get(speaker_col, ""))
    if not speaker:
        return text

    if text.lower().startswith(f"{speaker.lower()}:"):
        return text

    return f"{speaker}: {text}"


def _build_transcript(rows: pd.DataFrame, text_col: str, speaker_col: Optional[str]) -> str:
    """Join one or many dataset rows into a readable transcript block."""
    rows = _sort_rows_for_transcript(rows)
    transcript_parts = [
        _format_transcript_row(row, text_col, speaker_col)
        for _, row in rows.iterrows()
    ]
    return "\n\n".join(part for part in transcript_parts if part)


def _looks_like_ungrouped_turn_table(df: pd.DataFrame, text_col: str, speaker_col: Optional[str]) -> bool:
    """Detect a single meeting transcript spread across rows without a meeting id."""
    if len(df) < MIN_ROWS_FOR_UNGROUPED_TURN_TRANSCRIPT:
        return False

    texts = _sample_nonempty_texts(df, text_col)
    if len(texts) < MIN_ROWS_FOR_UNGROUPED_TURN_TRANSCRIPT:
        return False

    avg_len = sum(len(text) for text in texts) / len(texts)
    has_order_col = _find_column(df, ORDER_COLUMN_KEYWORDS) is not None
    has_turn_signals = speaker_col is not None or has_order_col

    return has_turn_signals and avg_len <= SHORT_TURN_AVG_CHARS


def _row_title(row: pd.Series, title_col: Optional[str], fallback: str) -> str:
    if not title_col:
        return fallback
    title = _text_from_value(row.get(title_col, ""))
    return title or fallback


def _first_nonempty_row_index(df: pd.DataFrame, text_col: str, speaker_col: Optional[str]) -> Optional[int]:
    for idx, row in df.iterrows():
        if _format_transcript_row(row, text_col, speaker_col):
            return idx
    return None


def _group_values(df: pd.DataFrame, group_col: Optional[str]) -> list:
    if not group_col:
        return []
    return [value for value in df[group_col].dropna().unique().tolist() if str(value).strip()]


def _detected_mode(df: pd.DataFrame, text_col: str, group_col: Optional[str], speaker_col: Optional[str]) -> str:
    """Infer the most likely processing mode from dataset shape and content."""
    if group_col and df[group_col].notna().any() and df[group_col].duplicated().any():
        return DATASET_MODE_GROUPED_ROWS
    if _looks_like_ungrouped_turn_table(df, text_col, speaker_col):
        return DATASET_MODE_UNGROUPED_COMBINED
    return DATASET_MODE_SINGLE_ROW


class DatasetLoader:
    """Load dataset files and extract one transcript sample from common shapes."""

    def __init__(self, dataset_dir: str = "data/dataset"):
        self.dataset_dir = dataset_dir

    def get_available_files(self) -> list[str]:
        """Lists supported dataset files in the dataset directory."""
        if not os.path.exists(self.dataset_dir):
            return []
        
        return [
            f for f in os.listdir(self.dataset_dir)
            if f.lower().endswith(SUPPORTED_DATASET_EXTENSIONS)
        ]

    def load_dataset(self, filename: str) -> pd.DataFrame:
        """Loads a dataset file."""
        file_path = os.path.join(self.dataset_dir, filename)
        extension = os.path.splitext(filename)[1].lower()
        try:
            if extension == '.csv':
                return pd.read_csv(file_path)
            if extension == '.parquet':
                return pd.read_parquet(file_path)
            if extension == '.json':
                return pd.read_json(file_path)
            if extension in {'.jsonl', '.ndjson'}:
                return pd.read_json(file_path, lines=True)
        except Exception as e:
            logger.error(f"Error loading dataset {filename}: {e}")
        return pd.DataFrame()

    def get_dataset_profile(self, df: pd.DataFrame) -> dict:
        """Describe how the loader sees a dataset before processing it."""
        if df.empty:
            return {
                "row_count": 0,
                "columns": [],
                "text_column": None,
                "group_column": None,
                "speaker_column": None,
                "title_column": None,
                "detected_mode": None,
                "group_count": 0,
            }

        text_col = _find_text_column(df)
        speaker_col = _find_column(df, SPEAKER_COLUMN_KEYWORDS)
        title_col = _find_column(df, TITLE_COLUMN_KEYWORDS)
        group_col = _find_group_column(df, text_col) if text_col else None

        return {
            "row_count": len(df),
            "columns": [str(col) for col in df.columns],
            "text_column": str(text_col) if text_col else None,
            "group_column": str(group_col) if group_col else None,
            "speaker_column": str(speaker_col) if speaker_col else None,
            "title_column": str(title_col) if title_col else None,
            "detected_mode": _detected_mode(df, text_col, group_col, speaker_col) if text_col else None,
            "group_count": len(_group_values(df, group_col)),
        }

    def detect_processing_mode(self, df: pd.DataFrame) -> Optional[str]:
        """Return the mode the loader would automatically choose for a dataset."""
        profile = self.get_dataset_profile(df)
        return profile.get("detected_mode")

    def _build_grouped_sample(self, df: pd.DataFrame, text_col: str, group_col: str, speaker_col: Optional[str]) -> Optional[dict]:
        """Build one transcript from rows that share the same meeting identifier."""
        group_values = _group_values(df, group_col)
        if not group_values:
            return None

        selected_group = random.choice(group_values)
        rows = df[df[group_col] == selected_group]
        transcript = _build_transcript(rows, text_col, speaker_col)
        if not transcript:
            return None

        return {
            "title": f"Meeting {selected_group} ({len(rows)} dataset rows combined)",
            "transcript": transcript,
            "metadata": {
                "dataset_mode": DATASET_MODE_GROUPED_ROWS,
                "group_column": str(group_col),
                "text_column": str(text_col),
                "selected_group": str(selected_group),
                "rows_combined": len(rows),
            },
        }

    def _build_combined_sample(self, df: pd.DataFrame, text_col: str, speaker_col: Optional[str], mode: str) -> Optional[dict]:
        """Combine every row into one transcript when the dataset is one meeting."""
        transcript = _build_transcript(df, text_col, speaker_col)
        if not transcript:
            return None

        return {
            "title": f"Combined transcript from {len(df)} dataset rows",
            "transcript": transcript,
            "metadata": {
                "dataset_mode": mode,
                "text_column": str(text_col),
                "speaker_column": str(speaker_col) if speaker_col else None,
                "rows_combined": len(df),
            },
        }

    def _build_single_row_sample(
        self,
        df: pd.DataFrame,
        text_col: str,
        speaker_col: Optional[str],
        title_col: Optional[str],
    ) -> Optional[dict]:
        """Pick one row when each row already represents a full transcript."""
        idx = random.randint(0, len(df) - 1)
        row = df.iloc[idx]
        transcript = _format_transcript_row(row, text_col, speaker_col)
        if not transcript:
            # If the random row is empty, fall back to the first usable row so
            # preview and processing still work on imperfect datasets.
            fallback_idx = _first_nonempty_row_index(df, text_col, speaker_col)
            if fallback_idx is None:
                logger.error("Selected dataset did not contain transcript text.")
                return None
            idx = fallback_idx
            row = df.loc[idx]
            transcript = _format_transcript_row(row, text_col, speaker_col)

        return {
            "title": _row_title(row, title_col, f"Random sample: {text_col} row {idx} of {len(df)}"),
            "transcript": transcript,
            "metadata": {
                "dataset_mode": DATASET_MODE_SINGLE_ROW,
                "text_column": str(text_col),
                "selected_row": idx,
            },
        }

    def get_random_sample(self, df: pd.DataFrame, mode: str = DATASET_MODE_AUTO) -> Optional[dict]:
        """Gets a random full meeting transcript from many common dataset shapes.

        Supported shapes:
        - one row contains one complete meeting transcript
        - many rows contain turns/items for the same meeting and share a meeting id
        - optional speaker columns are merged into "Speaker: text" transcript lines
        - one meeting transcript spread across rows without a meeting id
        - transcript cells containing JSON/list/dict turn structures
        """
        if df.empty:
            return None
        if mode not in DATASET_MODES:
            logger.warning("Unknown dataset mode '%s'; falling back to auto detection.", mode)
            mode = DATASET_MODE_AUTO

        text_col = _find_text_column(df)
        if not text_col:
            logger.error("Could not find a transcript column in the dataset.")
            return None

        group_col = _find_group_column(df, text_col)
        speaker_col = _find_column(df, SPEAKER_COLUMN_KEYWORDS)
        title_col = _find_column(df, TITLE_COLUMN_KEYWORDS)
        detected_mode = _detected_mode(df, text_col, group_col, speaker_col)

        if mode == DATASET_MODE_GROUPED_ROWS:
            if not group_col:
                logger.error("Grouped rows mode was selected, but no group column was detected.")
                return None
            return self._build_grouped_sample(df, text_col, group_col, speaker_col)

        if mode == DATASET_MODE_COMBINE_ALL:
            return self._build_combined_sample(df, text_col, speaker_col, DATASET_MODE_COMBINE_ALL)

        if mode == DATASET_MODE_SINGLE_ROW:
            return self._build_single_row_sample(df, text_col, speaker_col, title_col)

        # Auto mode uses the same detected mode reported in the dataset profile
        # so preview and processing remain consistent.
        if detected_mode == DATASET_MODE_GROUPED_ROWS:
            return self._build_grouped_sample(df, text_col, group_col, speaker_col)

        if detected_mode == DATASET_MODE_UNGROUPED_COMBINED:
            return self._build_combined_sample(df, text_col, speaker_col, DATASET_MODE_UNGROUPED_COMBINED)

        return self._build_single_row_sample(df, text_col, speaker_col, title_col)
