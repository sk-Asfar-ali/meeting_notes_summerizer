from app.tools.summarize_meeting import summarize_and_extract
from app.tools.extract_actions import process_extracted_actions
from app.llm.ollama_client import OllamaClient
import logging

logger = logging.getLogger(__name__)

class SummarizerAgent:
    def __init__(self, llm_client: OllamaClient):
        self.llm_client = llm_client

    def process_transcript(self, meeting_id: str, transcript: str, past_context: str = "") -> dict:
        """Generates summary, decisions, risks, and extracts actions."""
        logger.info(f"SummarizerAgent processing transcript for meeting {meeting_id}")
        
        # 1. Summarize and extract raw JSON data
        raw_summary_data = summarize_and_extract(transcript, self.llm_client, past_context)
        
        # 2. Process action items into structured format
        action_items = process_extracted_actions(meeting_id, raw_summary_data.get('action_items', []))
        
        # 3. Compile final summary dictionary
        summary_dict = {
            "meeting_id": meeting_id,
            "executive_summary": raw_summary_data.get('executive_summary', ''),
            "bullet_highlights": raw_summary_data.get('bullet_highlights', []),
            "decisions": raw_summary_data.get('decisions', []),
            "risks_blockers": raw_summary_data.get('risks_blockers', []),
            "action_items": action_items
        }
        
        return summary_dict
