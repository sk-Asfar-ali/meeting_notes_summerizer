"""Extract transcript text from uploaded files before they enter the pipeline."""

from io import BytesIO
from pathlib import Path
from typing import BinaryIO

import pandas as pd

from app.services.dataset_loader import DATASET_MODE_COMBINE_ALL, DatasetLoader


UPLOAD_FILE_TYPES = [
    "txt",
    "text",
    "md",
    "markdown",
    "log",
    "srt",
    "vtt",
    "pdf",
    "csv",
    "tsv",
    "json",
    "jsonl",
    "ndjson",
    "parquet",
    "xls",
    "xlsx",
]

TEXT_EXTENSIONS = {"txt", "text", "md", "markdown", "log", "srt", "vtt"}
TABULAR_EXTENSIONS = {"csv", "tsv", "json", "jsonl", "ndjson", "parquet"}
EXCEL_EXTENSIONS = {"xls", "xlsx"}


class TranscriptFileError(ValueError):
    """Raised when an uploaded file cannot be turned into transcript text."""

    pass


def _read_bytes(uploaded_file: BinaryIO) -> bytes:
    """Read bytes from Streamlit/FastAPI-style upload objects."""
    if hasattr(uploaded_file, "getvalue"):
        return uploaded_file.getvalue()
    return uploaded_file.read()


def _decode_text(content: bytes) -> str:
    """Decode uploaded text while tolerating a few common encodings."""
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return content.decode(encoding).strip()
        except UnicodeDecodeError:
            continue
    raise TranscriptFileError("Could not decode this text file.")


def _read_pdf(content: bytes) -> str:
    """Extract selectable text from PDF pages."""
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise TranscriptFileError("PDF upload requires the pypdf package. Install project requirements first.") from exc

    reader = PdfReader(BytesIO(content))
    page_text = []
    for page in reader.pages:
        text = page.extract_text() or ""
        if text.strip():
            page_text.append(text.strip())

    transcript = "\n\n".join(page_text).strip()
    if not transcript:
        raise TranscriptFileError("No selectable text was found in this PDF.")
    return transcript


def _read_tabular(content: bytes, extension: str) -> pd.DataFrame:
    """Load a supported tabular upload into a DataFrame."""
    stream = BytesIO(content)
    if extension == "csv":
        return pd.read_csv(stream)
    if extension == "tsv":
        return pd.read_csv(stream, sep="\t")
    if extension == "parquet":
        return pd.read_parquet(stream)
    if extension == "json":
        return pd.read_json(stream)
    if extension in {"jsonl", "ndjson"}:
        return pd.read_json(stream, lines=True)
    raise TranscriptFileError(f"Unsupported tabular file type: .{extension}")


def _sample_from_dataframe(df: pd.DataFrame, filename: str, metadata: dict | None = None) -> dict:
    """Convert a tabular upload into one transcript sample for processing."""
    sample = DatasetLoader().get_random_sample(df, mode=DATASET_MODE_COMBINE_ALL)
    if not sample:
        raise TranscriptFileError("Could not extract transcript text from this file.")

    sample["title"] = f"Uploaded file: {filename}"
    sample["metadata"] = {
        **sample.get("metadata", {}),
        **(metadata or {}),
        "source_file": filename,
    }
    return sample


def _read_excel(content: bytes, filename: str, extension: str) -> dict:
    """Read all useful sheets from an Excel workbook and merge them into text."""
    try:
        sheets = pd.read_excel(BytesIO(content), sheet_name=None)
    except ImportError as exc:
        package_name = "openpyxl" if extension == "xlsx" else "xlrd"
        raise TranscriptFileError(
            f"Excel .{extension} upload requires the {package_name} package. Install project requirements first."
        ) from exc

    transcript_parts = []
    total_rows = 0
    for sheet_name, df in sheets.items():
        if df.empty:
            continue
        sample = DatasetLoader().get_random_sample(df, mode=DATASET_MODE_COMBINE_ALL)
        if not sample:
            continue
        total_rows += len(df)
        transcript_parts.append(f"[Sheet: {sheet_name}]\n{sample['transcript']}")

    transcript = "\n\n".join(transcript_parts).strip()
    if not transcript:
        raise TranscriptFileError("Could not extract transcript text from this Excel file.")

    return {
        "title": f"Uploaded file: {filename}",
        "transcript": transcript,
        "metadata": {
            "dataset_mode": "uploaded_excel",
            "source_file": filename,
            "file_type": extension,
            "rows_combined": total_rows,
            "sheets_combined": len(transcript_parts),
        },
    }


def extract_uploaded_transcript(uploaded_file: BinaryIO) -> dict:
    """Extract one transcript from an uploaded text, document, or tabular file."""
    filename = getattr(uploaded_file, "name", "uploaded_file")
    extension = Path(filename).suffix.lower().lstrip(".")
    content = _read_bytes(uploaded_file)

    if not content:
        raise TranscriptFileError("Uploaded file is empty.")

    if extension in TEXT_EXTENSIONS:
        return {
            "title": f"Uploaded file: {filename}",
            "transcript": _decode_text(content),
            "metadata": {
                "dataset_mode": "uploaded_text",
                "source_file": filename,
                "file_type": extension,
            },
        }

    if extension == "pdf":
        return {
            "title": f"Uploaded file: {filename}",
            "transcript": _read_pdf(content),
            "metadata": {
                "dataset_mode": "uploaded_pdf",
                "source_file": filename,
                "file_type": extension,
            },
        }

    if extension in TABULAR_EXTENSIONS:
        df = _read_tabular(content, extension)
        return _sample_from_dataframe(
            df,
            filename,
            {
                "dataset_mode": "uploaded_tabular",
                "file_type": extension,
                "rows_combined": len(df),
            },
        )

    if extension in EXCEL_EXTENSIONS:
        return _read_excel(content, filename, extension)

    raise TranscriptFileError(f"Unsupported file type: .{extension}")
