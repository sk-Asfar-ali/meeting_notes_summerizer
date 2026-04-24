# Meeting Notes AI

A complete, locally-hosted, privacy-first AI application for summarizing meeting transcripts, extracting action items, and interacting with past meetings via semantic search.

## Features
* **100% Local**: No API keys, no data sent to the cloud.
* **Resource Efficient**: Designed explicitly to run smoothly on laptops with 8GB RAM.
* **Kaggle Dataset Support**: Automatically loads and samples from your CSV/Parquet datasets.
* **Semantic Search**: Chat with your meeting transcripts using RAG (Retrieval-Augmented Generation).

## Prerequisites
1. Python 3.11+
2. [Ollama](https://ollama.com/) installed on your machine.

## Setup Instructions

### 1. Install and Start Ollama
Download and install Ollama from [ollama.com](https://ollama.com/).
Once installed, open your terminal and pull the lightweight model:
```bash
ollama run llama3.2
```
*(Leave Ollama running in the background, or ensure the service is active).*

### 2. Install Python Dependencies
Open your terminal in this project's root directory (`meeting-notes-ai`):
```bash
pip install -r requirements.txt
```

### 3. Add Datasets (Optional)
If you have Kaggle dataset files (`train_df`, `test_df`, `validate_df` in CSV or Parquet format), place them inside the `data/dataset/` directory.

### 4. Run the Application
```bash
streamlit run streamlit_app.py
```

## Architecture
- **UI**: Streamlit
- **LLM**: Ollama (`llama3.2`)
- **Embeddings**: `sentence-transformers/all-MiniLM-L6-v2`
- **Databases**: SQLite (structured data) + ChromaDB (semantic search)

For detailed architectural rationale, please read the `evaluator_guide.md`.
