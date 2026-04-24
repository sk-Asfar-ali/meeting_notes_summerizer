from app.tools.clean_text import clean_transcript
from app.tools.chunk_text import chunk_transcript
from app.tools.extract_actions import process_extracted_actions

def test_clean_transcript():
    raw_text = "This   is \n\n a test\n."
    cleaned = clean_transcript(raw_text)
    assert cleaned == "This is\n a test\n."

def test_chunk_transcript():
    text = " ".join(["word"] * 100)
    chunks = chunk_transcript(text, max_words=60, overlap=10)
    assert len(chunks) == 2
    assert len(chunks[0].split()) == 60

def test_process_extracted_actions():
    raw_actions = [
        {"task": "Do X", "owner": "Alice", "deadline": "Tomorrow"}
    ]
    processed = process_extracted_actions("meeting_123", raw_actions)
    assert len(processed) == 1
    assert processed[0]['meeting_id'] == "meeting_123"
    assert processed[0]['task'] == "Do X"
    assert processed[0]['owner'] == "Alice"
    assert processed[0]['status'] == "Pending"
    assert 'id' in processed[0]
