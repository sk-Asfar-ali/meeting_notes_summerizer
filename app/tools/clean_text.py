import re

def clean_transcript(text: str) -> str:
    """Removes excessive whitespace and weird characters from transcript."""
    if not text:
        return ""
    # Remove multiple spaces/newlines
    text = re.sub(r'\n+', '\n', text)
    text = re.sub(r'\s{2,}', ' ', text)
    # Remove unusual unicode characters but keep punctuation
    text = text.encode('ascii', 'ignore').decode()
    return text.strip()
