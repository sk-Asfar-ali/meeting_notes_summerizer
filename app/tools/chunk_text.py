"""Split long transcripts into overlapping chunks for embedding search."""

def chunk_transcript(text: str, max_words: int = 800, overlap: int = 100) -> list[str]:
    """Splits transcript into overlapping chunks for embedding."""
    if not text:
        return []
        
    words = text.split()
    chunks = []
    
    if len(words) <= max_words:
        return [text]
        
    # Overlap keeps some continuity between neighboring chunks so retrieval has
    # a better chance of capturing full thoughts.
    for i in range(0, len(words), max_words - overlap):
        chunk = " ".join(words[i:i + max_words])
        chunks.append(chunk)
        if i + max_words >= len(words):
            break
            
    return chunks
