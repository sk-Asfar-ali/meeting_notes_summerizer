"""FastAPI entry point for the meeting notes backend.

This module wires HTTP routes to the agent layer and returns frontend-friendly
payloads for processing, search, and chat.
"""

import json
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.agents.memory_agent import MemoryAgent
from app.agents.orchestrator_agent import OrchestratorAgent
from app.agents.summarizer_agent import SummarizerAgent
from app.llm.ollama_client import OllamaClient
from app.memory.sqlite_store import SQLiteStore
from app.memory.vector_store import VectorStore
from app.services.dataset_loader import DATASET_MODE_AUTO, DatasetLoader
from app.services.transcript_file_loader import TranscriptFileError, extract_uploaded_transcript


class NamedBytesIO(BytesIO):
    """Bytes buffer that mimics an uploaded file object with a stable name."""

    def __init__(self, content: bytes, name: str):
        super().__init__(content)
        self.name = name


class ProcessTextRequest(BaseModel):
    text: str
    title: str = "Manually Uploaded Meeting"


class DatasetRequest(BaseModel):
    filename: str
    mode: Optional[str] = None


class ChatRequest(BaseModel):
    question: str


class Services:
    """Container for the long-lived backend objects used across requests."""

    def __init__(self):
        self.sqlite_store = SQLiteStore()
        self.vector_store = VectorStore()
        self.llm_client = OllamaClient()
        self.summarizer_agent = SummarizerAgent(self.llm_client)
        self.memory_agent = MemoryAgent(self.sqlite_store, self.vector_store)
        self.orchestrator = OrchestratorAgent(
            self.summarizer_agent,
            self.memory_agent,
            self.llm_client,
        )
        self.dataset_loader = DatasetLoader()


status_llm_client = OllamaClient()
app = FastAPI(title="Meeting Notes API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@lru_cache(maxsize=1)
def get_services() -> Services:
    """Create the service graph once and reuse it across API requests."""
    return Services()


def _parse_metadata(meeting: dict[str, Any]) -> dict[str, Any]:
    """Decode meeting metadata stored as JSON text in SQLite."""
    try:
        return json.loads(meeting.get("metadata") or "{}")
    except json.JSONDecodeError:
        return {}


def _meeting_payload(meeting_id: str) -> dict[str, Any]:
    """Return the combined meeting + summary payload expected by the frontend."""
    service = get_services()
    meeting = service.sqlite_store.get_meeting(meeting_id)
    summary = service.sqlite_store.get_summary(meeting_id)
    if not meeting or not summary:
        raise HTTPException(status_code=404, detail="Meeting not found")

    return {
        "meeting": {
            "id": meeting["id"],
            "title": meeting["title"],
            "date": meeting["date"],
            "metadata": _parse_metadata(meeting),
        },
        "summary": summary,
    }


def _sample_from_dataset(request: DatasetRequest) -> dict[str, Any]:
    """Load a dataset file and extract one representative transcript sample."""
    service = get_services()
    df = service.dataset_loader.load_dataset(request.filename)
    if df.empty:
        raise HTTPException(status_code=400, detail="Dataset file is empty or could not be loaded")

    profile = service.dataset_loader.get_dataset_profile(df)
    requested_mode = request.mode or DATASET_MODE_AUTO
    sample = service.dataset_loader.get_random_sample(df, mode=requested_mode)
    if not sample:
        raise HTTPException(status_code=400, detail="Could not extract a transcript sample from this dataset")
    return {"profile": profile, "sample": sample}


@app.get("/api/status")
def status():
    """Health check for the frontend so it can show model availability."""
    return {
        "model": status_llm_client.model_name,
        "online": status_llm_client.check_model_availability(),
    }


@app.get("/api/datasets")
def datasets():
    """List dataset files available for preview or processing."""
    return {"files": get_services().dataset_loader.get_available_files()}


@app.post("/api/datasets/preview")
def preview_dataset(request: DatasetRequest):
    """Preview one extracted transcript without storing it."""
    payload = _sample_from_dataset(request)
    sample = payload["sample"]
    return {
        "profile": payload["profile"],
        "sample": {
            "title": sample["title"],
            "metadata": sample.get("metadata", {}),
            "preview": sample["transcript"][:2500],
            "char_count": len(sample["transcript"]),
        },
    }


@app.post("/api/datasets/process")
def process_dataset(request: DatasetRequest):
    """Process one transcript sampled from a dataset and persist the result."""
    payload = _sample_from_dataset(request)
    sample = payload["sample"]
    meeting_id = get_services().orchestrator.process_new_meeting(
        sample["transcript"],
        title=sample["title"],
        metadata=sample.get("metadata", {}),
    )
    return {"meeting_id": meeting_id, **_meeting_payload(meeting_id)}


@app.post("/api/transcripts/text")
def process_text(request: ProcessTextRequest):
    """Process raw transcript text pasted into the UI."""
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Transcript text is empty")

    meeting_id = get_services().orchestrator.process_new_meeting(
        request.text,
        title=request.title,
        metadata={"dataset_mode": "pasted_text"},
    )
    return {"meeting_id": meeting_id, **_meeting_payload(meeting_id)}


@app.post("/api/transcripts/upload")
async def process_upload(file: UploadFile = File(...), title: Optional[str] = Form(None)):
    """Process an uploaded transcript file after extracting plain text from it."""
    content = await file.read()
    try:
        sample = extract_uploaded_transcript(NamedBytesIO(content, file.filename or "uploaded_file"))
    except TranscriptFileError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if title and title.strip():
        sample["title"] = title.strip()

    meeting_id = get_services().orchestrator.process_new_meeting(
        sample["transcript"],
        title=sample["title"],
        metadata=sample.get("metadata", {}),
    )
    return {"meeting_id": meeting_id, **_meeting_payload(meeting_id)}


@app.get("/api/meetings")
def meetings():
    """Return saved meetings for the sidebar list."""
    return {"meetings": get_services().sqlite_store.get_all_meetings()}


@app.get("/api/meetings/{meeting_id}")
def meeting_detail(meeting_id: str):
    """Return one stored meeting and its summary."""
    return _meeting_payload(meeting_id)


@app.get("/api/search")
def search_meetings(q: str):
    """Semantic search across previously saved meetings."""
    return {"results": get_services().memory_agent.search_history(q)}


@app.post("/api/meetings/{meeting_id}/chat")
def chat(meeting_id: str, request: ChatRequest):
    """Answer a question about a specific meeting using retrieval + the LLM."""
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question is empty")
    return {
        "answer": get_services().orchestrator.chat_about_meeting(meeting_id, request.question),
    }


frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if frontend_dist.exists():
    # When the React app has been built, the API can also serve the static UI.
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
