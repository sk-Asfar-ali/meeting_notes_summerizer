import os
from app.llm.ollama_client import OllamaClient
from app.tools.summarize_meeting import summarize_and_extract

with open('test_transcript.txt', 'r') as f:
    text = f.read()

client = OllamaClient()

print("\n--- SUMMARIZER AGENT OUTPUT ---")
summarized = summarize_and_extract(text, client)
import json
print(json.dumps(summarized, indent=2))
