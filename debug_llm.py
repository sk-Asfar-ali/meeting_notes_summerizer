"""Small manual script for checking the local LLM summarization flow."""

import json

from app.llm.ollama_client import OllamaClient
from app.tools.summarize_meeting import summarize_and_extract

with open("test_transcript.txt", "r") as f:
    text = f.read()

client = OllamaClient()

print("\n--- SUMMARIZER AGENT OUTPUT ---")
summarized = summarize_and_extract(text, client)
print(json.dumps(summarized, indent=2))
