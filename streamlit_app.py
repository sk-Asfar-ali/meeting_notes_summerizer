"""Legacy Streamlit UI for the meeting notes application.

The React + FastAPI stack is the primary interface now, but this file still
offers a single-process UI that exercises the same backend agents directly.
"""

import json

import pandas as pd
import streamlit as st

from app.agents.memory_agent import MemoryAgent
from app.agents.orchestrator_agent import OrchestratorAgent
from app.agents.summarizer_agent import SummarizerAgent
from app.llm.ollama_client import OllamaClient
from app.memory.sqlite_store import SQLiteStore
from app.memory.vector_store import VectorStore
from app.services.dataset_loader import (
    DATASET_MODE_AUTO,
    DatasetLoader,
)
from app.services.transcript_file_loader import (
    UPLOAD_FILE_TYPES,
    TranscriptFileError,
    extract_uploaded_transcript,
)


@st.cache_resource
def init_services():
    """Create one shared set of stores, agents, and loaders for the app session."""
    sqlite_store = SQLiteStore()
    vector_store = VectorStore()
    llm_client = OllamaClient()

    summarizer_agent = SummarizerAgent(llm_client)
    memory_agent = MemoryAgent(sqlite_store, vector_store)
    orchestrator = OrchestratorAgent(summarizer_agent, memory_agent, llm_client)
    dataset_loader = DatasetLoader()

    return sqlite_store, vector_store, llm_client, orchestrator, dataset_loader


def reset_current_meeting(meeting_id: str | None = None):
    """Reset the active meeting view and clear any meeting-specific chat history."""
    st.session_state.current_meeting_id = meeting_id
    st.session_state.chat_history = []


def render_dataset_caption(metadata: dict):
    """Render a human-readable description of how the current transcript was sourced."""
    mode = metadata.get("dataset_mode")
    if mode == "grouped_rows":
        st.caption(
            f"Dataset source: combined {metadata.get('rows_combined')} rows "
            f"from {metadata.get('group_column')} = {metadata.get('selected_group')}"
        )
    elif mode == "single_row":
        st.caption(
            f"Dataset source: single row {metadata.get('selected_row')} "
            f"from column {metadata.get('text_column')}"
        )
    elif mode in {"ungrouped_rows_combined", "combine_all_rows"}:
        st.caption(
            f"Dataset source: combined {metadata.get('rows_combined')} rows "
            f"from column {metadata.get('text_column')}"
        )
    elif mode in {"uploaded_text", "uploaded_pdf", "uploaded_tabular", "uploaded_excel", "pasted_text"}:
        source = metadata.get("source_file", "pasted text")
        file_type = metadata.get("file_type")
        detail = f" ({file_type})" if file_type else ""
        st.caption(f"Transcript source: {source}{detail}")


st.set_page_config(page_title="Meeting Notes Summariser", layout="wide")

# Initialize the shared service layer once, then reuse it across reruns.
sqlite_store, vector_store, llm_client, orchestrator, dataset_loader = init_services()

# Streamlit reruns the script often, so session state keeps the selected meeting
# and chat history stable between button clicks.
if "current_meeting_id" not in st.session_state:
    st.session_state.current_meeting_id = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "dataset_preview" not in st.session_state:
    st.session_state.dataset_preview = None


with st.sidebar:
    st.title("Meeting Notes Summariser")

    model_status = "Online" if llm_client.check_model_availability() else "Offline"
    st.write(f"Model ({llm_client.model_name}): {model_status}")
    if model_status == "Offline":
        st.error(f"Please run `ollama run {llm_client.model_name}` in your terminal.")

    st.subheader("1. Upload Transcript")
    uploaded_file = st.file_uploader(
        "Choose a transcript file",
        type=UPLOAD_FILE_TYPES,
    )
    raw_text_input = st.text_area("Or Paste Transcript Here:")

    if st.button("Process Transcript"):
        uploaded_sample = None
        if uploaded_file:
            try:
                uploaded_sample = extract_uploaded_transcript(uploaded_file)
            except TranscriptFileError as exc:
                st.error(str(exc))
        elif raw_text_input.strip():
            uploaded_sample = {
                "title": "Manually Uploaded Meeting",
                "transcript": raw_text_input.strip(),
                "metadata": {"dataset_mode": "pasted_text"},
            }

        if uploaded_sample:
            with st.spinner("Processing with local LLM..."):
                # The orchestrator handles the full backend pipeline end to end.
                meeting_id = orchestrator.process_new_meeting(
                    uploaded_sample["transcript"],
                    title=uploaded_sample["title"],
                    metadata=uploaded_sample.get("metadata", {}),
                )
                reset_current_meeting(meeting_id)
                st.success("Meeting processed successfully!")
                st.rerun()
        else:
            st.warning("Please upload a file or paste text.")

    st.subheader("2. Load from Dataset")
    files = dataset_loader.get_available_files()
    if files:
        selected_file = st.selectbox("Select Dataset File", files)

        if st.button("Preview Dataset Sample"):
            with st.spinner("Loading sample..."):
                df = dataset_loader.load_dataset(selected_file)
                profile = dataset_loader.get_dataset_profile(df)
                # Preview uses the same loader heuristics as real processing.
                sample = dataset_loader.get_random_sample(df, mode=DATASET_MODE_AUTO)
                if sample:
                    st.session_state.dataset_preview = {
                        "file": selected_file,
                        "profile": profile,
                        "sample": sample,
                    }
                else:
                    st.error("Failed to load sample.")

        preview = st.session_state.dataset_preview
        if preview and preview.get("file") == selected_file:
            profile = preview["profile"]
            sample = preview["sample"]
            sample_mode = sample.get("metadata", {}).get("dataset_mode")

            st.caption(
                f"Detected: {profile.get('detected_mode') or 'unknown'} | "
                f"text: {profile.get('text_column') or '-'} | "
                f"group: {profile.get('group_column') or '-'} | "
                f"speaker: {profile.get('speaker_column') or '-'}"
            )
            st.text_area(
                "Preview",
                sample["transcript"][:1500],
                height=160,
                disabled=True,
            )
            st.caption(f"Rows: {profile.get('row_count', 0)} | Sample mode: {sample_mode}")

            if st.button("Process Previewed Sample"):
                with st.spinner("Processing with local LLM..."):
                    meeting_id = orchestrator.process_new_meeting(
                        sample["transcript"],
                        title=sample["title"],
                        metadata=sample.get("metadata", {}),
                    )
                    reset_current_meeting(meeting_id)
                    st.session_state.dataset_preview = None
                    st.success("Sample processed!")
                    st.rerun()
    else:
        st.info("No datasets found in data/dataset/")

    st.subheader("3. Past Meetings")
    meetings = sqlite_store.get_all_meetings()
    if meetings:
        meeting_options = {
            f"{meeting['title']} ({meeting['date'][:10]})": meeting["id"]
            for meeting in meetings
        }
        selected_meeting_label = st.selectbox("Open saved meeting", list(meeting_options.keys()))
        if st.button("Load Saved Meeting"):
            reset_current_meeting(meeting_options[selected_meeting_label])
            st.rerun()
    else:
        st.caption("No saved meetings yet.")


st.title("Meeting Dashboard")

if not st.session_state.current_meeting_id:
    st.info("Please process a transcript or select a past meeting to view details.")

    st.subheader("Search Past Meetings")
    search_query = st.text_input("Semantic search across all past meetings...")
    if search_query:
        # Search runs against the vector store over saved meeting summaries.
        results = orchestrator.memory_agent.search_history(search_query)
        if results:
            for result in results:
                st.write(f"**{result['title']}** (ID: {result['meeting_id']})")
                st.write(f"> {result['summary_snippet']}")
                if st.button(f"Load Meeting {result['meeting_id']}", key=result["meeting_id"]):
                    reset_current_meeting(result["meeting_id"])
                    st.rerun()
        else:
            st.write("No matching meetings found.")
else:
    summary_data = sqlite_store.get_summary(st.session_state.current_meeting_id)
    meeting_data = sqlite_store.get_meeting(st.session_state.current_meeting_id)

    if summary_data and meeting_data:
        st.header(meeting_data["title"])
        try:
            metadata = json.loads(meeting_data.get("metadata") or "{}")
        except Exception:
            metadata = {}

        render_dataset_caption(metadata)

        tab1, tab2, tab3, tab4, tab5 = st.tabs(
            ["Summary", "Decisions", "Action Items", "Risks", "Chat with Meeting"]
        )

        with tab1:
            st.subheader("Executive Summary")
            st.write(summary_data.get("executive_summary", "No summary available."))

            st.subheader("Key Highlights")
            for bullet in summary_data.get("bullet_highlights", []):
                st.markdown(f"- {bullet}")

        with tab2:
            st.subheader("Decisions Made")
            decisions = summary_data.get("decisions", [])
            if decisions:
                for decision in decisions:
                    st.markdown(f"- {decision}")
            else:
                st.write("No decisions were extracted.")

        with tab3:
            st.subheader("Action Items")
            actions = summary_data.get("action_items", [])
            if actions:
                df_actions = pd.DataFrame(actions)[["task", "owner", "deadline", "status"]]
                st.dataframe(df_actions, use_container_width=True)
            else:
                st.write("No action items extracted.")

        with tab4:
            st.subheader("Risks & Blockers")
            risks = summary_data.get("risks_blockers", [])
            if risks:
                for risk in risks:
                    st.markdown(f"- {risk}")
            else:
                st.write("No risks or blockers were extracted for this meeting.")

        with tab5:
            st.subheader("Chat with Transcript")

            for message in st.session_state.chat_history:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

            if prompt := st.chat_input("Ask a question about this meeting..."):
                st.session_state.chat_history.append({"role": "user", "content": prompt})
                with st.chat_message("user"):
                    st.markdown(prompt)

                with st.chat_message("assistant"):
                    with st.spinner("Thinking..."):
                        # Chat retrieves relevant transcript chunks for this meeting,
                        # then asks the LLM to answer using only that context.
                        response = orchestrator.chat_about_meeting(
                            st.session_state.current_meeting_id,
                            prompt,
                        )
                        st.markdown(response)
                        st.session_state.chat_history.append(
                            {"role": "assistant", "content": response}
                        )

        st.divider()
        if st.button("Clear Current Meeting"):
            reset_current_meeting()
            st.rerun()
    else:
        st.error("Could not load the selected meeting.")
