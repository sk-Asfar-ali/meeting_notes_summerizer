def chunk_transcript(text: str, max_words: int = 400, overlap: int = 50) -> list[str]:
    """Splits transcript into overlapping chunks for embedding."""
    if not text:
        return []
        
    words = text.split()
    chunks = []
    
    if len(words) <= max_words:
        return [text]
        
    for i in range(0, len(words), max_words - overlap):
        chunk = " ".join(words[i:i + max_words])
        chunks.append(chunk)
        if i + max_words >= len(words):
            break
            
    return chunks
