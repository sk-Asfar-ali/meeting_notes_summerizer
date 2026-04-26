"""Agent that owns storage, retrieval, and semantic search responsibilities."""

from app.memory.sqlite_store import SQLiteStore
from app.memory.vector_store import VectorStore
from app.tools.save_meeting import save_meeting_data
from app.tools.search_meetings import search_past_meetings
from app.tools.retrieve_context import retrieve_transcript_context

class MemoryAgent:
    """Thin abstraction over the structured and vector memory layers."""

    def __init__(self, sqlite_store: SQLiteStore, vector_store: VectorStore):
        self.sqlite_store = sqlite_store
        self.vector_store = vector_store

    def store_meeting(self, meeting_dict: dict, summary_dict: dict, transcript_chunks: list[str]):
        """Stores all meeting data across SQLite and ChromaDB."""
        save_meeting_data(meeting_dict, summary_dict, self.sqlite_store, self.vector_store, transcript_chunks)

    def search_history(self, query: str, n_results: int = 5) -> list[dict]:
        """Searches past meetings via vector store."""
        return search_past_meetings(query, self.vector_store, n_results)

    def retrieve_transcript_snippet(self, meeting_id: str, query: str, n_results: int = 3) -> str:
        """Retrieves specific chunks of a transcript for chat context."""
        return retrieve_transcript_context(meeting_id, query, self.vector_store, n_results)
