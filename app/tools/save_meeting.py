"""Helpers for persisting structured and semantic meeting data together."""

from app.memory.sqlite_store import SQLiteStore
from app.memory.vector_store import VectorStore

def save_meeting_data(meeting_dict: dict, summary_dict: dict, sqlite_store: SQLiteStore, vector_store: VectorStore, transcript_chunks: list[str]):
    """Saves meeting metadata to SQLite and embeddings to ChromaDB."""
    # 1. Save to SQLite
    sqlite_store.save_meeting(meeting_dict)
    sqlite_store.save_summary(summary_dict)
    
    # 2. Save transcript chunks to Vector DB for chat
    if transcript_chunks:
        vector_store.add_transcript_chunks(meeting_dict['id'], transcript_chunks)
        
    # 3. Save summary text to Vector DB for past-meeting search
    combined_summary = summary_dict.get('executive_summary', '') + "\n" + "\n".join(summary_dict.get('bullet_highlights', []))
    vector_store.add_meeting_summary(meeting_dict['id'], meeting_dict.get('title', 'Untitled'), combined_summary)
