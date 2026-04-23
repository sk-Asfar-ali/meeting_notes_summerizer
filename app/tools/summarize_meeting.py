import json
from app.llm.ollama_client import OllamaClient
from app.llm.prompts import SYSTEM_PROMPT_JSON, SUMMARIZE_MEETING_PROMPT

def summarize_and_extract(transcript: str, llm_client: OllamaClient) -> dict:
    """Uses LLM to summarize the meeting and extract structured data."""
    prompt = SUMMARIZE_MEETING_PROMPT.format(transcript=transcript)
    
    response_text = llm_client.generate(
        prompt=prompt,
        system_prompt=SYSTEM_PROMPT_JSON,
        json_format=True
    )
    
    try:
        data = json.loads(response_text)
        return data
    except json.JSONDecodeError:
        # Fallback if model fails to return valid JSON
        return {
            "executive_summary": "Error: Failed to parse summary from LLM.",
            "bullet_highlights": [],
            "decisions": [],
            "risks_blockers": [],
            "action_items": []
        }
