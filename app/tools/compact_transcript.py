"""Trim very large transcripts to a budget that local models can handle well."""

import os
import re


DEFAULT_MAX_CHARS = 14000

IMPORTANT_LINE_RE = re.compile(
    r"\b("
    r"action|assign|assigned|blocker|deadline|decid(?:e|ed|ing)|decision|"
    r"due|follow[- ]?up|need to|next step|owner|risk|todo|will"
    r")\b",
    re.IGNORECASE,
)


def get_llm_transcript_char_limit() -> int:
    """Return the transcript budget used for local LLM summarization."""
    raw_value = os.getenv("MEETING_LLM_MAX_CHARS", str(DEFAULT_MAX_CHARS))
    try:
        return max(4000, int(raw_value))
    except ValueError:
        return DEFAULT_MAX_CHARS


def compact_transcript_for_llm(transcript: str, max_chars: int | None = None) -> str:
    """Reduce very large transcripts while preserving likely summary/action lines.

    Local models slow down sharply as prompt size grows. This keeps normal
    transcripts untouched, and for large uploads keeps the opening, ending, and
    lines most likely to contain decisions, risks, deadlines, or actions.
    """
    if not transcript:
        return ""

    limit = max_chars or get_llm_transcript_char_limit()
    if len(transcript) <= limit:
        return transcript

    marker = (
        "\n\n[Transcript compacted for speed. Kept the beginning, ending, "
        "and lines likely to contain decisions, risks, deadlines, and actions.]\n\n"
    )
    available = limit - len(marker)
    if available <= 0:
        return transcript[:limit]

    head_budget = int(available * 0.35)
    tail_budget = int(available * 0.25)
    important_budget = available - head_budget - tail_budget

    # Preserve the start and end of the meeting, then try to rescue important
    # lines from the middle where decisions and assignments often appear.
    head = transcript[:head_budget].rsplit("\n", 1)[0].strip()
    tail = transcript[-tail_budget:].split("\n", 1)[-1].strip()

    middle = transcript[head_budget:-tail_budget]
    important_lines = []
    used = 0
    for line in middle.splitlines():
        line = line.strip()
        if not line or not IMPORTANT_LINE_RE.search(line):
            continue
        line_len = len(line) + 1
        if used + line_len > important_budget:
            break
        important_lines.append(line)
        used += line_len

    important = "\n".join(important_lines).strip()
    compacted_parts = [part for part in (head, important, tail) if part]
    return marker.join(compacted_parts)[:limit]
