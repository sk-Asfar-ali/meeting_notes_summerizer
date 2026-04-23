from app.memory.vector_store import VectorStore

def retrieve_transcript_context(meeting_id: str, query: str, vector_store: VectorStore, n_results: int = 3) -> str:
    """Retrieves relevant transcript chunks for a specific query."""
    results = vector_store.search_transcript(meeting_id, query, n_results)
    if not results:
        return ""
    return "\n...\n".join(results)
