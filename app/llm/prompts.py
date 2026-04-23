SYSTEM_PROMPT_JSON = """You are an expert meeting assistant. You MUST output your response strictly in valid JSON format. Do not include any markdown formatting like ```json or ``` in the output. Just raw JSON."""

SUMMARIZE_MEETING_PROMPT = """Analyze the following meeting transcript.
Extract the following information:
1. An executive summary (a paragraph describing the main topic and outcome)
2. Bullet highlights (3-5 key points discussed)
3. Decisions made (list of clear decisions agreed upon)
4. Risks and blockers (any identified issues, delays, or dependencies)
5. Action items (tasks with their assigned owner and deadline if mentioned)

Meeting Transcript:
{transcript}

Output strictly valid JSON matching this schema:
{{
  "executive_summary": "string",
  "bullet_highlights": ["string", "string"],
  "decisions": ["string", "string"],
  "risks_blockers": ["string", "string"],
  "action_items": [
    {{
      "task": "string",
      "owner": "string or 'Unassigned'",
      "deadline": "string or 'None'"
    }}
  ]
}}"""

CHAT_SYSTEM_PROMPT = """You are a helpful AI assistant answering questions about a meeting. Use the provided context from the meeting transcript and summary to answer the user's question accurately. If the answer is not in the context, say "I don't have enough information from the meeting to answer that." """

CHAT_PROMPT = """Context from meeting:
{context}

User Question: {question}

Answer:"""
