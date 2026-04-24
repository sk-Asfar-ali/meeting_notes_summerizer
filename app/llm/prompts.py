SYSTEM_PROMPT_JSON = """You are an expert meeting assistant. You MUST output your response strictly in valid JSON format. Do not include any markdown formatting like ```json or ``` in the output. Just raw JSON."""

SUMMARIZE_MEETING_PROMPT = """Analyze the following meeting transcript.
You are provided with context from similar past meetings to help you maintain continuity. 
CRITICAL INSTRUCTION: You MUST extract bullet highlights, decisions, risks, and action items ONLY from the "Meeting Transcript" section below. Do NOT extract action items or decisions from the "Past Meetings Context".

CRITICAL EDGE CASE RULES (MUST FOLLOW STRICTLY):
1. Speaker Normalization: Normalize speaker names and resolve minor spelling differences. If a speaker is unknown or unclear, assign "UNKNOWN_SPEAKER" as the owner for their tasks.
2. Retractions & Corrections: If a speaker corrects themselves (e.g., using words like 'actually', 'wait', 'sorry', 'correction'), completely IGNORE their earlier superseded statement.
3. Implicit / Unassigned Action Items: If a task is mentioned vaguely (e.g., "someone should...", "we need to..."), extract it as an action item and set the owner to "Unassigned".
4. Hypotheticals vs Decisions: If an idea is conditional or proposed (e.g., using 'if', 'could', 'might', 'maybe'), NEVER extract it as a decision or action item.
5. Relative Dates: If a time reference lacks an exact date (e.g., "next Friday", "tomorrow"), preserve it exactly as is (e.g., "RELATIVE: next Friday").
6. Filler Words & STT Noise: Ignore and filter out words like 'uh', 'um', 'you know', or repeated words when pulling out facts.
7. Multiple Actions: If a sentence contains multiple tasks (e.g., "I will test the API and update the docs"), split them into separate distinct action items.
8. Greetings & Small Talk: Ignore small talk, greetings, or system messages (e.g., "Recording started", "Hi everyone", "Thanks, bye") when creating your summary.

Past Meetings Context (FOR REFERENCE ONLY):
{past_context}

Meeting Transcript:
{transcript}

Extract the following information strictly from the Meeting Transcript:
1. An executive summary (a paragraph describing the main topic and outcome)
2. Bullet highlights (3-5 key points discussed)
3. Decisions made (list of clear decisions agreed upon)
4. Risks and blockers (any identified issues, delays, or dependencies)
5. Action items (tasks with their assigned owner and deadline, ONLY if mentioned)

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
