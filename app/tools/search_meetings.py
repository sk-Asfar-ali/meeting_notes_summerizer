from app.memory.vector_store import VectorStore

def search_past_meetings(query: str, vector_store: VectorStore, n_results: int = 5) -> list[dict]:
    """Semantic search over all past meeting summaries."""
    return vector_store.search_past_meetings(query, n_results=n_results)
