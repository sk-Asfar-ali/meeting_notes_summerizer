import streamlit as st
import os
import pandas as pd
from app.llm.ollama_client import OllamaClient
from app.memory.sqlite_store import SQLiteStore
from app.memory.vector_store import VectorStore
from app.agents.summarizer_agent import SummarizerAgent
from app.agents.memory_agent import MemoryAgent
from app.agents.orchestrator_agent import OrchestratorAgent
from app.services.dataset_loader import DatasetLoader

# Initialize Services
@st.cache_resource
def init_services():
    sqlite_store = SQLiteStore()
    vector_store = VectorStore()
    llm_client = OllamaClient()
    
    summarizer_agent = SummarizerAgent(llm_client)
    memory_agent = MemoryAgent(sqlite_store, vector_store)
    orchestrator = OrchestratorAgent(summarizer_agent, memory_agent, llm_client)
    dataset_loader = DatasetLoader()
    
    return sqlite_store, vector_store, llm_client, orchestrator, dataset_loader

st.set_page_config(page_title="Meeting Notes Summariser", layout="wide")

sqlite_store, vector_store, llm_client, orchestrator, dataset_loader = init_services()

# App State
if "current_meeting_id" not in st.session_state:
    st.session_state.current_meeting_id = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# Sidebar
with st.sidebar:
    st.title("⚙️ Meeting Notes Summariser")
    
    model_status = "🟢 Online" if llm_client.check_model_availability() else "🔴 Offline"
    st.write(f"Model ({llm_client.model_name}): {model_status}")
    if model_status == "🔴 Offline":
        st.error(f"Please run `ollama run {llm_client.model_name}` in your terminal.")

    st.subheader("1. Upload Transcript")
    uploaded_file = st.file_uploader("Choose a TXT file", type=["txt"])
    raw_text_input = st.text_area("Or Paste Transcript Here:")
    
    if st.button("Process Transcript"):
        text_to_process = ""
        if uploaded_file:
            text_to_process = uploaded_file.read().decode("utf-8")
        elif raw_text_input:
            text_to_process = raw_text_input
            
        if text_to_process:
            with st.spinner("Processing with local LLM (this may take a minute)..."):
                meeting_id = orchestrator.process_new_meeting(text_to_process, title="Manually Uploaded Meeting")
                st.session_state.current_meeting_id = meeting_id
                st.session_state.chat_history = []
                st.success("Meeting processed successfully!")
                st.rerun()
        else:
            st.warning("Please upload a file or paste text.")

    st.subheader("2. Load from Dataset")
    files = dataset_loader.get_available_files()
    if files:
        selected_file = st.selectbox("Select Dataset File", files)
        if st.button("Load Random Sample"):
            with st.spinner("Loading sample..."):
                df = dataset_loader.load_dataset(selected_file)
                sample = dataset_loader.get_random_sample(df)
                if sample:
                    meeting_id = orchestrator.process_new_meeting(sample['transcript'], title=sample['title'])
                    st.session_state.current_meeting_id = meeting_id
                    st.session_state.chat_history = []
                    st.success("Sample processed!")
                    st.rerun()
                else:
                    st.error("Failed to load sample.")
    else:
        st.info("No datasets found in data/dataset/")

# Main UI
st.title("📊 Meeting Dashboard")

if not st.session_state.current_meeting_id:
    st.info("Please process a transcript or select a past meeting to view details.")

    st.subheader("Search Past Meetings")
    search_query = st.text_input("Semantic search across all past meetings...")
    if search_query:
        results = orchestrator.memory_agent.search_history(search_query)
        if results:
            for r in results:
                st.write(f"**{r['title']}** (ID: {r['meeting_id']})")
                st.write(f"> {r['summary_snippet']}")
                if st.button(f"Load Meeting {r['meeting_id']}", key=r['meeting_id']):
                    st.session_state.current_meeting_id = r['meeting_id']
                    st.session_state.chat_history = []
                    st.rerun()
        else:
            st.write("No matching meetings found.")

else:
    # Load current meeting data
    summary_data = sqlite_store.get_summary(st.session_state.current_meeting_id)
    meeting_data = sqlite_store.get_meeting(st.session_state.current_meeting_id)
    
    if summary_data and meeting_data:
        st.header(meeting_data['title'])
        
        tab1, tab2, tab3, tab4, tab5 = st.tabs(["Summary", "Decisions", "Action Items", "Risks", "Chat with Meeting"])
        
        with tab1:
            st.subheader("Executive Summary")
            st.write(summary_data.get('executive_summary', 'No summary available.'))
            
            st.subheader("Key Highlights")
            for bullet in summary_data.get('bullet_highlights', []):
                st.markdown(f"- {bullet}")
                
        with tab2:
            st.subheader("Decisions Made")
            for decision in summary_data.get('decisions', []):
                st.markdown(f"✅ {decision}")
                
        with tab3:
            st.subheader("Action Items")
            actions = summary_data.get('action_items', [])
            if actions:
                # Convert to dataframe for nice table display
                df_actions = pd.DataFrame(actions)[['task', 'owner', 'deadline', 'status']]
                st.dataframe(df_actions, use_container_width=True)
            else:
                st.write("No action items extracted.")
                
        with tab4:
            st.subheader("Risks & Blockers")
            for risk in summary_data.get('risks_blockers', []):
                st.markdown(f"⚠️ {risk}")
                
        with tab5:
            st.subheader("Chat with Transcript")
            
            # Display chat history
            for message in st.session_state.chat_history:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])
                    
            # Chat input
            if prompt := st.chat_input("Ask a question about this meeting..."):
                st.session_state.chat_history.append({"role": "user", "content": prompt})
                with st.chat_message("user"):
                    st.markdown(prompt)
                    
                with st.chat_message("assistant"):
                    with st.spinner("Thinking..."):
                        response = orchestrator.chat_about_meeting(st.session_state.current_meeting_id, prompt)
                        st.markdown(response)
                        st.session_state.chat_history.append({"role": "assistant", "content": response})
        
        st.divider()
        if st.button("Clear Current Meeting"):
            st.session_state.current_meeting_id = None
            st.rerun()
