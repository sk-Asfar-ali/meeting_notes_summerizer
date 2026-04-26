"""Prompt-building, LLM calling, and response parsing for meeting summaries."""

import json
import logging
import re
from typing import Any

from pydantic import BaseModel, Field, ValidationError, field_validator

from app.llm.ollama_client import OllamaClient
from app.llm.prompts import (
    MERGE_MEETING_SUMMARIES_PROMPT,
    SUMMARIZE_MEETING_CHUNK_PROMPT,
    SUMMARIZE_MEETING_PROMPT,
    SYSTEM_PROMPT_JSON,
)
from app.tools.compact_transcript import get_llm_transcript_char_limit

logger = logging.getLogger(__name__)


class RawActionItem(BaseModel):
    task: str = "Unknown task"
    owner: str = "Unassigned"
    deadline: str = "None"

    @field_validator("task", "owner", "deadline", mode="before")
    @classmethod
    def stringify_value(cls, value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()


class RawMeetingSummary(BaseModel):
    executive_summary: str = ""
    bullet_highlights: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    risks_blockers: list[str] = Field(default_factory=list)
    action_items: list[RawActionItem] = Field(default_factory=list)

    @field_validator("executive_summary", mode="before")
    @classmethod
    def stringify_summary(cls, value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()

    @field_validator("bullet_highlights", "decisions", "risks_blockers", mode="before")
    @classmethod
    def normalize_string_list(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value.strip()] if value.strip() else []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return [str(value).strip()] if str(value).strip() else []


def _fallback_summary() -> dict:
    """Return a safe empty structure when model output cannot be parsed."""
    return {
        "executive_summary": "Error: Failed to parse summary from LLM.",
        "bullet_highlights": [],
        "decisions": [],
        "risks_blockers": [],
        "action_items": [],
    }


def _log_parse_failure(stage: str, response_text: str, error: Exception) -> None:
    """Log the parser failure with a short preview of the raw model output."""
    preview = _strip_markdown_fence(response_text).replace("\n", "\\n")
    if len(preview) > 500:
        preview = f"{preview[:500]}..."
    logger.warning("%s parse failed: %s | response preview: %s", stage, error, preview)


def _strip_markdown_fence(text: str) -> str:
    """Remove ```json fences that models sometimes add despite instructions."""
    stripped = text.strip()
    match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", stripped, flags=re.IGNORECASE | re.DOTALL)
    return match.group(1).strip() if match else stripped


def _extract_json_object(text: str) -> str:
    """Extract the first balanced JSON object from a noisy model response."""
    stripped = _strip_markdown_fence(text)
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped

    start = stripped.find("{")
    if start == -1:
        raise json.JSONDecodeError("No JSON object found", stripped, 0)

    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(stripped)):
        char = stripped[index]
        if escape:
            escape = False
            continue
        if char == "\\":
            escape = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return stripped[start:index + 1]

    raise json.JSONDecodeError("Unclosed JSON object", stripped, start)


def parse_summary_response(response_text: str) -> dict:
    """Parse and validate the meeting-summary JSON returned by the LLM."""
    data = json.loads(_extract_json_object(response_text))
    summary = RawMeetingSummary.model_validate(data)
    return summary.model_dump()


def _split_transcript_for_summary(
    transcript: str,
    max_chars: int,
    overlap_chars: int | None = None,
) -> list[str]:
    """Split a large transcript into overlapping chunks for safer extraction."""
    if not transcript:
        return []
    if len(transcript) <= max_chars:
        return [transcript]

    overlap = overlap_chars if overlap_chars is not None else min(max(50, max_chars // 10), max_chars // 3)
    overlap = max(0, min(overlap, max_chars - 1))

    chunks = []
    start = 0
    text_length = len(transcript)
    while start < text_length:
        end = min(text_length, start + max_chars)
        if end < text_length:
            split_at = transcript.rfind("\n", start + (max_chars // 2), end)
            if split_at > start:
                end = split_at + 1

        chunk = transcript[start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end >= text_length:
            break

        next_start = end - overlap
        if next_start <= start:
            next_start = end
        start = next_start

    return chunks


def _summarize_chunk(
    transcript_chunk: str,
    llm_client: OllamaClient,
    past_context: str,
    chunk_index: int,
    total_chunks: int,
) -> dict:
    """Extract structured data from one transcript chunk."""
    if total_chunks == 1:
        prompt = SUMMARIZE_MEETING_PROMPT.format(
            transcript=transcript_chunk,
            past_context=past_context if past_context else "No similar past meetings found.",
        )
    else:
        prompt = SUMMARIZE_MEETING_CHUNK_PROMPT.format(
            chunk_index=chunk_index,
            total_chunks=total_chunks,
            transcript=transcript_chunk,
            past_context=past_context if past_context else "No similar past meetings found.",
        )

    response_text = llm_client.generate(
        prompt=prompt,
        system_prompt=SYSTEM_PROMPT_JSON,
        json_format=True,
    )

    try:
        return parse_summary_response(response_text)
    except (json.JSONDecodeError, ValidationError) as error:
        _log_parse_failure("Chunk summary", response_text, error)
        return _fallback_summary()


def _normalize_text_key(value: str) -> str:
    """Normalize strings before deduplication."""
    return re.sub(r"\s+", " ", (value or "").strip()).lower()


def _dedupe_strings(items: list[str]) -> list[str]:
    """Deduplicate string lists while preserving order."""
    seen = set()
    deduped = []
    for item in items:
        key = _normalize_text_key(item)
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(item.strip())
    return deduped


def _dedupe_action_items(action_items: list[dict]) -> list[dict]:
    """Deduplicate action items produced by overlapping transcript chunks."""
    seen = set()
    deduped = []
    for item in action_items:
        key = (
            _normalize_text_key(item.get("task", "")),
            _normalize_text_key(item.get("owner", "Unassigned")),
            _normalize_text_key(item.get("deadline", "None")),
        )
        if not key[0] or key in seen:
            continue
        seen.add(key)
        deduped.append(
            {
                "task": item.get("task", "Unknown task"),
                "owner": item.get("owner", "Unassigned") or "Unassigned",
                "deadline": item.get("deadline", "None") or "None",
            }
        )
    return deduped


def _merge_chunk_summaries_fallback(chunk_summaries: list[dict]) -> dict:
    """Merge chunk summaries deterministically if the final LLM merge fails."""
    executive_summaries = [
        summary.get("executive_summary", "").strip()
        for summary in chunk_summaries
        if summary.get("executive_summary", "").strip()
        and not summary.get("executive_summary", "").startswith("Error:")
    ]
    combined_exec = " ".join(executive_summaries[:3]).strip()
    if len(executive_summaries) > 3:
        combined_exec += " ..."

    bullet_highlights = _dedupe_strings(
        [item for summary in chunk_summaries for item in summary.get("bullet_highlights", [])]
    )[:5]
    decisions = _dedupe_strings(
        [item for summary in chunk_summaries for item in summary.get("decisions", [])]
    )
    risks_blockers = _dedupe_strings(
        [item for summary in chunk_summaries for item in summary.get("risks_blockers", [])]
    )
    action_items = _dedupe_action_items(
        [item for summary in chunk_summaries for item in summary.get("action_items", []) if isinstance(item, dict)]
    )

    return {
        "executive_summary": combined_exec or "Meeting summary compiled from chunk-level extraction.",
        "bullet_highlights": bullet_highlights,
        "decisions": decisions,
        "risks_blockers": risks_blockers,
        "action_items": action_items,
    }


def _merge_chunk_summaries(chunk_summaries: list[dict], llm_client: OllamaClient) -> dict:
    """Ask the LLM to combine chunk summaries into one whole-meeting summary."""
    if len(chunk_summaries) == 1:
        return chunk_summaries[0]

    all_chunk_bullets = [item for summary in chunk_summaries for item in summary.get("bullet_highlights", [])]
    all_chunk_decisions = [item for summary in chunk_summaries for item in summary.get("decisions", [])]
    all_chunk_risks = [item for summary in chunk_summaries for item in summary.get("risks_blockers", [])]
    all_chunk_actions = [
        item for summary in chunk_summaries for item in summary.get("action_items", []) if isinstance(item, dict)
    ]

    prompt = MERGE_MEETING_SUMMARIES_PROMPT.format(
        chunk_summaries=json.dumps(chunk_summaries, ensure_ascii=True, indent=2),
    )
    response_text = llm_client.generate(
        prompt=prompt,
        system_prompt=SYSTEM_PROMPT_JSON,
        json_format=True,
    )
    try:
        merged = parse_summary_response(response_text)
        # Keep the LLM's polished merged wording, but union it with all chunk
        # outputs so no decision, blocker, or action item disappears during merge.
        merged["decisions"] = _dedupe_strings(merged.get("decisions", []) + all_chunk_decisions)
        merged["risks_blockers"] = _dedupe_strings(merged.get("risks_blockers", []) + all_chunk_risks)
        merged["bullet_highlights"] = _dedupe_strings(merged.get("bullet_highlights", []) + all_chunk_bullets)[:5]
        merged["action_items"] = _dedupe_action_items(merged.get("action_items", []) + all_chunk_actions)
        return merged
    except (json.JSONDecodeError, ValidationError) as error:
        _log_parse_failure("Merged summary", response_text, error)
        return _merge_chunk_summaries_fallback(chunk_summaries)


def summarize_and_extract(transcript: str, llm_client: OllamaClient, past_context: str = "") -> dict:
    """Summarize a meeting safely by covering the full transcript in chunks."""
    chunk_size = get_llm_transcript_char_limit()
    transcript_chunks = _split_transcript_for_summary(transcript, max_chars=chunk_size)
    if not transcript_chunks:
        return _fallback_summary()

    chunk_summaries = [
        _summarize_chunk(
            transcript_chunk=chunk,
            llm_client=llm_client,
            past_context=past_context,
            chunk_index=index,
            total_chunks=len(transcript_chunks),
        )
        for index, chunk in enumerate(transcript_chunks, start=1)
    ]
    return _merge_chunk_summaries(chunk_summaries, llm_client)
