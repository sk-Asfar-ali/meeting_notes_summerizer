import chromadb
from chromadb.utils import embedding_functions
import os

class VectorStore:
    def __init__(self, persist_directory: str = "data/chroma_db"):
        self.persist_directory = persist_directory
        os.makedirs(self.persist_directory, exist_ok=True)
        self.client = chromadb.PersistentClient(path=self.persist_directory)
        
        # Use a lightweight sentence-transformers model
        self.embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        
        # Collections for different types of searches
        self.transcript_collection = self.client.get_or_create_collection(
            name="transcripts", 
            embedding_function=self.embedding_function
        )
        
        self.meeting_summary_collection = self.client.get_or_create_collection(
            name="meeting_summaries",
            embedding_function=self.embedding_function
        )

    def add_transcript_chunks(self, meeting_id: str, chunks: list[str]):
        """Store transcript chunks for a specific meeting (useful for chat-with-transcript)."""
        ids = [f"{meeting_id}_chunk_{i}" for i in range(len(chunks))]
        metadatas = [{"meeting_id": meeting_id, "chunk_index": i} for i in range(len(chunks))]
        
        # Upsert allows updating if already exists
        self.transcript_collection.upsert(
            documents=chunks,
            metadatas=metadatas,
            ids=ids
        )

    def search_transcript(self, meeting_id: str, query: str, n_results: int = 3):
        """Search within a specific meeting's transcript."""
        results = self.transcript_collection.query(
            query_texts=[query],
            n_results=n_results,
            where={"meeting_id": meeting_id}
        )
        if results and results['documents'] and len(results['documents']) > 0:
            return results['documents'][0]
        return []

    def add_meeting_summary(self, meeting_id: str, title: str, summary_text: str):
        """Store the summary to search across past meetings."""
        self.meeting_summary_collection.upsert(
            documents=[summary_text],
            metadatas=[{"meeting_id": meeting_id, "title": title}],
            ids=[meeting_id]
        )

    def search_past_meetings(self, query: str, n_results: int = 3):
        """Semantic search across all past meetings."""
        if self.meeting_summary_collection.count() == 0:
            return []
            
        n_results = min(n_results, self.meeting_summary_collection.count())
        results = self.meeting_summary_collection.query(
            query_texts=[query],
            n_results=n_results
        )
        
        formatted_results = []
        if results and results['documents'] and len(results['documents']) > 0:
            for i in range(len(results['documents'][0])):
                formatted_results.append({
                    "meeting_id": results['metadatas'][0][i]['meeting_id'],
                    "title": results['metadatas'][0][i]['title'],
                    "summary_snippet": results['documents'][0][i]
                })
        return formatted_results
