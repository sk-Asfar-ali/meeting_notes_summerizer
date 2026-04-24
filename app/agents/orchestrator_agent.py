from app.tools.ingest_transcript import ingest_raw_transcript
from app.tools.clean_text import clean_transcript
from app.tools.chunk_text import chunk_transcript
from app.agents.summarizer_agent import SummarizerAgent
from app.agents.memory_agent import MemoryAgent
from app.llm.ollama_client import OllamaClient
from app.llm.prompts import CHAT_SYSTEM_PROMPT, CHAT_PROMPT
import logging

logger = logging.getLogger(__name__)

class OrchestratorAgent:
    def __init__(self, summarizer_agent: SummarizerAgent, memory_agent: MemoryAgent, llm_client: OllamaClient):
        self.summarizer_agent = summarizer_agent
        self.memory_agent = memory_agent
        self.llm_client = llm_client

    def process_new_meeting(self, raw_text: str, title: str = "Untitled Meeting", metadata: dict = None) -> str:
        """End-to-end pipeline for processing a new transcript."""
        logger.info(f"Orchestrator processing new meeting: {title}")
        
        # 1. Clean Text
        cleaned_text = clean_transcript(raw_text)
        
        # 2. Ingest
        meeting_dict = ingest_raw_transcript(cleaned_text, title, metadata)
        meeting_id = meeting_dict['id']
        
        # 3. Chunk for Vector DB
        chunks = chunk_transcript(cleaned_text)
        
        # 4. Fetch Past Context (RAG)
        search_query = f"{title} {cleaned_text[:500]}"
        past_meetings = self.memory_agent.search_history(search_query, n_results=3)
        
        past_context = ""
        if past_meetings:
            for pm in past_meetings:
                past_context += f"Meeting: {pm['title']}\nSummary: {pm['summary_snippet']}\n\n"
                
        # 5. Summarize and Extract (using SummarizerAgent)
        # Note: If transcript is extremely long, we might need to map-reduce, 
        # but for simplicity and 8GB RAM limit, we assume it fits in context window of llama3.2 (up to 128k tokens typically)
        summary_dict = self.summarizer_agent.process_transcript(meeting_id, cleaned_text, past_context)
        
        # 5. Save to Memory (using MemoryAgent)
        self.memory_agent.store_meeting(meeting_dict, summary_dict, chunks)
        
        logger.info(f"Meeting {meeting_id} processed and saved.")
        return meeting_id

    def chat_about_meeting(self, meeting_id: str, question: str) -> str:
        """Answers a question about a specific meeting using RAG."""
        # Retrieve context from vector db
        context = self.memory_agent.retrieve_transcript_snippet(meeting_id, question)
        
        if not context:
            return "I couldn't find relevant information in the meeting transcript."
            
        prompt = CHAT_PROMPT.format(context=context, question=question)
        response = self.llm_client.generate(prompt=prompt, system_prompt=CHAT_SYSTEM_PROMPT)
        
        return response
