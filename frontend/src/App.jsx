/* Main React UI for uploading, browsing, searching, and chatting with meetings. */

import { useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  Bot,
  CheckCircle2,
  Database,
  FileText,
  FolderOpen,
  Loader2,
  MessageSquare,
  RefreshCw,
  Search,
  Send,
  Upload,
} from "lucide-react";

const UPLOAD_ACCEPT = [
  ".txt",
  ".text",
  ".md",
  ".markdown",
  ".log",
  ".srt",
  ".vtt",
  ".pdf",
  ".csv",
  ".tsv",
  ".json",
  ".jsonl",
  ".ndjson",
  ".parquet",
  ".xls",
  ".xlsx",
].join(",");

async function api(path, options = {}) {
  // Centralize fetch handling so every component gets the same JSON parsing
  // and readable error messages from the backend.
  const response = await fetch(path, options);
  const contentType = response.headers.get("content-type") || "";
  const body = contentType.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) {
    throw new Error(body?.detail || body || "Request failed");
  }
  return body;
}

function formatDate(value) {
  if (!value) return "Unknown date";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value).slice(0, 10);
  return date.toLocaleDateString();
}

function sourceCaption(metadata = {}) {
  const mode = metadata.dataset_mode;
  if (mode === "grouped_rows") {
    return `Combined ${metadata.rows_combined} rows from ${metadata.group_column} = ${metadata.selected_group}`;
  }
  if (mode === "single_row") {
    return `Single row ${metadata.selected_row} from ${metadata.text_column}`;
  }
  if (mode === "combine_all_rows" || mode === "ungrouped_rows_combined") {
    return `Combined ${metadata.rows_combined} rows from ${metadata.text_column}`;
  }
  if (mode?.startsWith("uploaded") || mode === "pasted_text") {
    const fileType = metadata.file_type ? ` (${metadata.file_type})` : "";
    return `${metadata.source_file || "Pasted transcript"}${fileType}`;
  }
  return "";
}

function StatusPill({ status }) {
  const online = Boolean(status?.online);
  return (
    <span className={`status-pill ${online ? "online" : "offline"}`}>
      {online ? <CheckCircle2 size={16} /> : <AlertCircle size={16} />}
      {status ? `${status.model}: ${online ? "Online" : "Offline"}` : "Checking model"}
    </span>
  );
}

function Sidebar({
  status,
  meetings,
  datasets,
  onRefresh,
  onLoadMeeting,
  onProcessedMeeting,
  currentMeetingId,
}) {
  const [uploadFile, setUploadFile] = useState(null);
  const [uploadTitle, setUploadTitle] = useState("");
  const [pastedText, setPastedText] = useState("");
  const [selectedDataset, setSelectedDataset] = useState("");
  const [datasetPreview, setDatasetPreview] = useState(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    // Default to the first dataset as soon as the backend reports available files.
    if (!selectedDataset && datasets.length) {
      setSelectedDataset(datasets[0]);
    }
  }, [datasets, selectedDataset]);

  async function processUpload() {
    setError("");
    setBusy("upload");
    try {
      let payload;
      if (uploadFile) {
        const form = new FormData();
        form.append("file", uploadFile);
        if (uploadTitle.trim()) form.append("title", uploadTitle.trim());
        // File uploads go to the backend extractor before entering the normal pipeline.
        payload = await api("/api/transcripts/upload", {
          method: "POST",
          body: form,
        });
      } else {
        // Pasted text skips file extraction and goes straight into processing.
        payload = await api("/api/transcripts/text", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            text: pastedText,
            title: uploadTitle.trim() || "Manually Uploaded Meeting",
          }),
        });
      }
      onProcessedMeeting(payload);
      setPastedText("");
      setUploadFile(null);
      setUploadTitle("");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy("");
    }
  }

  async function previewDataset() {
    setError("");
    setBusy("preview");
    try {
      const payload = await api("/api/datasets/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ filename: selectedDataset }),
      });
      setDatasetPreview(payload);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy("");
    }
  }

  async function processDataset() {
    setError("");
    setBusy("dataset");
    try {
      const payload = await api("/api/datasets/process", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ filename: selectedDataset }),
      });
      onProcessedMeeting(payload);
      setDatasetPreview(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy("");
    }
  }

  return (
    <aside className="sidebar">
      <div className="brand">
        <div>
          <h1>Meeting Notes</h1>
          <p>Local summariser</p>
        </div>
        <button className="icon-button" onClick={onRefresh} title="Refresh">
          <RefreshCw size={18} />
        </button>
      </div>

      <StatusPill status={status} />

      {error && <div className="error-banner">{error}</div>}

      <section className="panel">
        <h2><Upload size={18} /> Upload</h2>
        <input
          className="input"
          placeholder="Meeting title"
          value={uploadTitle}
          onChange={(event) => setUploadTitle(event.target.value)}
        />
        <label className="dropzone">
          <FileText size={22} />
          <span>{uploadFile ? uploadFile.name : "Choose transcript, PDF, spreadsheet, or dataset file"}</span>
          <input
            type="file"
            accept={UPLOAD_ACCEPT}
            onChange={(event) => setUploadFile(event.target.files?.[0] || null)}
          />
        </label>
        <textarea
          className="textarea"
          placeholder="Or paste transcript text"
          value={pastedText}
          onChange={(event) => setPastedText(event.target.value)}
          rows={5}
        />
        <button className="primary-button" onClick={processUpload} disabled={busy === "upload" || (!uploadFile && !pastedText.trim())}>
          {busy === "upload" ? <Loader2 className="spin" size={18} /> : <Upload size={18} />}
          Process
        </button>
      </section>

      <section className="panel">
        <h2><Database size={18} /> Dataset</h2>
        <select className="input" value={selectedDataset} onChange={(event) => setSelectedDataset(event.target.value)}>
          {datasets.map((file) => (
            <option key={file} value={file}>{file}</option>
          ))}
        </select>
        <div className="button-row">
          <button className="secondary-button" onClick={previewDataset} disabled={!selectedDataset || busy === "preview"}>
            {busy === "preview" ? <Loader2 className="spin" size={18} /> : <Search size={18} />}
            Preview
          </button>
          <button className="primary-button" onClick={processDataset} disabled={!selectedDataset || busy === "dataset"}>
            {busy === "dataset" ? <Loader2 className="spin" size={18} /> : <Upload size={18} />}
            Process
          </button>
        </div>
        {datasetPreview && (
          <div className="preview-box">
            {/* Preview helps the user confirm the loader understood the dataset shape correctly. */}
            <div className="meta-line">
              <span>{datasetPreview.profile.detected_mode || "unknown"}</span>
              <span>{datasetPreview.sample.char_count.toLocaleString()} chars</span>
            </div>
            <p>{datasetPreview.sample.preview}</p>
          </div>
        )}
      </section>

      <section className="panel">
        <h2><FolderOpen size={18} /> Meetings</h2>
        <div className="meeting-list">
          {meetings.length === 0 && <p className="muted">No saved meetings yet.</p>}
          {meetings.map((meeting) => (
            <button
              key={meeting.id}
              className={`meeting-link ${currentMeetingId === meeting.id ? "active" : ""}`}
              onClick={() => onLoadMeeting(meeting.id)}
            >
              <span>{meeting.title}</span>
              <small>{formatDate(meeting.date)}</small>
            </button>
          ))}
        </div>
      </section>
    </aside>
  );
}

function SummaryPanel({ detail }) {
  const [tab, setTab] = useState("summary");
  const summary = detail?.summary;
  const meeting = detail?.meeting;

  if (!summary || !meeting) {
    return (
      <main className="empty-state">
        <Bot size={42} />
        <h2>Process or open a meeting</h2>
        <p>Summaries, decisions, risks, action items, and chat appear here.</p>
      </main>
    );
  }

  const tabs = [
    ["summary", "Summary"],
    ["decisions", "Decisions"],
    ["actions", "Actions"],
    ["risks", "Risks"],
    ["chat", "Chat"],
  ];

  return (
    <main className="workspace">
      <header className="meeting-header">
        <div>
          <p className="eyebrow">{formatDate(meeting.date)}</p>
          <h1>{meeting.title}</h1>
          {sourceCaption(meeting.metadata) && <p className="source">{sourceCaption(meeting.metadata)}</p>}
        </div>
      </header>

      <nav className="tabs">
        {tabs.map(([value, label]) => (
          <button key={value} className={tab === value ? "active" : ""} onClick={() => setTab(value)}>
            {label}
          </button>
        ))}
      </nav>

      {tab === "summary" && (
        <section className="content-section">
          <h2>Executive Summary</h2>
          <p className="summary-text">{summary.executive_summary || "No summary available."}</p>
          <h2>Key Highlights</h2>
          <BulletList items={summary.bullet_highlights} empty="No highlights were extracted." />
        </section>
      )}

      {tab === "decisions" && (
        <section className="content-section">
          <h2>Decisions Made</h2>
          <BulletList items={summary.decisions} empty="No decisions were extracted." />
        </section>
      )}

      {tab === "actions" && (
        <section className="content-section">
          <h2>Action Items</h2>
          <ActionTable actions={summary.action_items || []} />
        </section>
      )}

      {tab === "risks" && (
        <section className="content-section">
          <h2>Risks & Blockers</h2>
          <BulletList items={summary.risks_blockers} empty="No risks or blockers were extracted." />
        </section>
      )}

      {tab === "chat" && <ChatPanel meetingId={meeting.id} />}
    </main>
  );
}

function BulletList({ items = [], empty }) {
  if (!items.length) return <p className="muted">{empty}</p>;
  return (
    <ul className="bullet-list">
      {items.map((item, index) => (
        <li key={`${item}-${index}`}>{item}</li>
      ))}
    </ul>
  );
}

function ActionTable({ actions }) {
  if (!actions.length) return <p className="muted">No action items extracted.</p>;
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Task</th>
            <th>Owner</th>
            <th>Deadline</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {actions.map((action) => (
            <tr key={action.id}>
              <td>{action.task}</td>
              <td>{action.owner || "Unassigned"}</td>
              <td>{action.deadline || "None"}</td>
              <td>{action.status || "Pending"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ChatPanel({ meetingId }) {
  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    // Reset the transient chat UI when the user opens a different meeting.
    setMessages([]);
    setQuestion("");
    setError("");
  }, [meetingId]);

  async function sendMessage(event) {
    event.preventDefault();
    if (!question.trim()) return;

    const userMessage = { role: "user", content: question.trim() };
    setMessages((current) => [...current, userMessage]);
    setQuestion("");
    setBusy(true);
    setError("");

    try {
      // The backend retrieves relevant transcript chunks before asking the LLM to answer.
      const payload = await api(`/api/meetings/${meetingId}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: userMessage.content }),
      });
      setMessages((current) => [...current, { role: "assistant", content: payload.answer }]);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="content-section chat-section">
      <h2><MessageSquare size={20} /> Chat with Meeting</h2>
      {error && <div className="error-banner">{error}</div>}
      <div className="messages">
        {messages.length === 0 && <p className="muted">Ask a question about the selected meeting.</p>}
        {messages.map((message, index) => (
          <div key={index} className={`message ${message.role}`}>
            {message.content}
          </div>
        ))}
      </div>
      <form className="chat-form" onSubmit={sendMessage}>
        <input
          className="input"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="Ask about actions, risks, decisions..."
        />
        <button className="primary-button icon-only" disabled={busy || !question.trim()} title="Send">
          {busy ? <Loader2 className="spin" size={18} /> : <Send size={18} />}
        </button>
      </form>
    </section>
  );
}

export default function App() {
  const [status, setStatus] = useState(null);
  const [datasets, setDatasets] = useState([]);
  const [meetings, setMeetings] = useState([]);
  const [detail, setDetail] = useState(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState([]);
  const [error, setError] = useState("");

  const currentMeetingId = detail?.meeting?.id;

  async function refreshShell() {
    setError("");
    try {
      // Load the shell data in parallel so the dashboard paints quickly.
      const [statusPayload, datasetPayload, meetingsPayload] = await Promise.all([
        api("/api/status"),
        api("/api/datasets"),
        api("/api/meetings"),
      ]);
      setStatus(statusPayload);
      setDatasets(datasetPayload.files || []);
      setMeetings(meetingsPayload.meetings || []);
    } catch (err) {
      setError(err.message);
    }
  }

  async function loadMeeting(meetingId) {
    setError("");
    try {
      setDetail(await api(`/api/meetings/${meetingId}`));
    } catch (err) {
      setError(err.message);
    }
  }

  async function runSearch(event) {
    event.preventDefault();
    if (!searchQuery.trim()) return;
    setError("");
    try {
      // Search is semantic rather than plain keyword matching.
      const payload = await api(`/api/search?q=${encodeURIComponent(searchQuery.trim())}`);
      setSearchResults(payload.results || []);
    } catch (err) {
      setError(err.message);
    }
  }

  function handleProcessedMeeting(payload) {
    // Processing endpoints return everything needed to immediately show the result.
    setDetail({ meeting: payload.meeting, summary: payload.summary });
    refreshShell();
  }

  useEffect(() => {
    // Populate the initial dashboard state on first render.
    refreshShell();
  }, []);

  // Reverse meetings once so the newest saved meetings appear first in the sidebar.
  const activeMeetings = useMemo(() => meetings.slice().reverse(), [meetings]);

  return (
    <div className="app-shell">
      <Sidebar
        status={status}
        meetings={activeMeetings}
        datasets={datasets}
        onRefresh={refreshShell}
        onLoadMeeting={loadMeeting}
        onProcessedMeeting={handleProcessedMeeting}
        currentMeetingId={currentMeetingId}
      />

      <div className="main-column">
        <header className="topbar">
          <form className="search" onSubmit={runSearch}>
            <Search size={18} />
            <input
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              placeholder="Search past meetings"
            />
          </form>
        </header>

        {error && <div className="error-banner page-error">{error}</div>}

        {searchResults.length > 0 && (
          <section className="search-results">
            {searchResults.map((result) => (
              <button key={result.meeting_id} onClick={() => loadMeeting(result.meeting_id)}>
                <strong>{result.title}</strong>
                <span>{result.summary_snippet}</span>
              </button>
            ))}
          </section>
        )}

        <SummaryPanel detail={detail} />
      </div>
    </div>
  );
}
