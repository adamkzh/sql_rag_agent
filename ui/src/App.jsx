import { useState } from "react";
import "./App.css";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export default function App() {
  const [query, setQuery] = useState("List VIP customers");
  const [response, setResponse] = useState(null);
  const [trace, setTrace] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const runQuery = async (e) => {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setError("");
    setResponse(null);
    setTrace([]);
    try {
      const res = await fetch(`${API_URL}/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query }),
      });
      if (!res.ok) {
        throw new Error(`Request failed: ${res.status}`);
      }
      const data = await res.json();
      setResponse(data.response);
      setTrace(data.trace || []);
    } catch (err) {
      setError(err.message || "Something went wrong");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page">
      <header className="topbar">
        <div>
          <p className="eyebrow">Resilient Agent Demo</p>
          <h1>SQL + Policy RAG Agent</h1>
          <p className="subhead">
            Route between SQL, docs, or hybrid. Watch every step in the trace.
          </p>
        </div>
        <div className="badge">Live</div>
      </header>

      <div className="columns">
        <section className="panel">
          <div className="panel-header">
            <div>
              <p className="eyebrow">User Interface</p>
              <h2>Ask a question</h2>
            </div>
          </div>

          <form className="form" onSubmit={runQuery}>
            <label htmlFor="query">Query</label>
            <textarea
              id="query"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              rows={3}
              placeholder="e.g. List VIP customers"
            />
            <button type="submit" disabled={loading}>
              {loading ? "Thinking..." : "Send to Agent"}
            </button>
          </form>

          {error && <div className="error">{error}</div>}

          {response && (
            <div className="result">
              {"message" in response && (
                <>
                  <p className="eyebrow">Message</p>
                  <p className="message">{response.message}</p>
                </>
              )}

              {"result" in response && response.result && (
                <>
                  <p className="eyebrow">Result</p>
                  {"error" in response.result ? (
                    <p className="error">Error: {response.result.error}</p>
                  ) : (
                    <ResultTable result={response.result} />
                  )}
                </>
              )}
            </div>
          )}
        </section>

        <section className="panel trace-panel">
          <div className="panel-header">
            <div>
              <p className="eyebrow">LLM Trace</p>
              <h2>Step-by-step log</h2>
            </div>
          </div>

          <div className="trace-list">
            {trace.length === 0 && (
              <p className="muted">Run a query to see the trace.</p>
            )}
            {trace.map((event, idx) => (
              <TraceItem key={idx} event={event} />
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}

function ResultTable({ result }) {
  if (!result.rows || result.rows.length === 0) {
    return <p className="muted">No rows returned.</p>;
  }

  return (
    <div className="table-wrapper">
      <table>
        <thead>
          <tr>
            {result.columns.map((col) => (
              <th key={col}>{col}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {result.rows.map((row, i) => (
            <tr key={i}>
              {result.columns.map((col) => (
                <td key={col}>{String(row[col])}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function TraceItem({ event }) {
  const entries = Object.entries(event);
  return (
    <div className="trace-item">
      <div className="trace-meta">
        <span className="pill">{event.step}</span>
        <span className="timestamp">{event.timestamp}</span>
      </div>
      <div className="kv-grid">
        {entries.map(([key, value]) => (
          <div className="kv-row" key={key}>
            <span className="kv-key">{key}</span>
            <span className="kv-value">{renderValue(value)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function renderValue(value) {
  if (value === null || value === undefined) return "—";
  if (Array.isArray(value)) return JSON.stringify(value, null, 2);
  if (typeof value === "object") return JSON.stringify(value, null, 2);
  return String(value);
}
