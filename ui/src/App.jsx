import { useEffect, useState } from "react";
import "./App.css";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export default function App() {
  const [activeTab, setActiveTab] = useState("agent");
  const [query, setQuery] = useState("List VIP customers");
  const [response, setResponse] = useState(null);
  const [trace, setTrace] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [dbData, setDbData] = useState(null);
  const [dbLoading, setDbLoading] = useState(false);
  const [dbError, setDbError] = useState("");
  const [policyContent, setPolicyContent] = useState("");
  const [policyLoading, setPolicyLoading] = useState(false);
  const [policyError, setPolicyError] = useState("");

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

  const loadDatabase = async () => {
    setDbLoading(true);
    setDbError("");
    try {
      const res = await fetch(`${API_URL}/database`);
      if (!res.ok) {
        throw new Error(`Request failed: ${res.status}`);
      }
      const data = await res.json();
      setDbData(data);
    } catch (err) {
      setDbError(err.message || "Unable to load database snapshot");
    } finally {
      setDbLoading(false);
    }
  };

  const loadPolicies = async () => {
    setPolicyLoading(true);
    setPolicyError("");
    try {
      const res = await fetch(`${API_URL}/policies`);
      if (!res.ok) {
        throw new Error(`Request failed: ${res.status}`);
      }
      const data = await res.json();
      setPolicyContent(data.content || "");
    } catch (err) {
      setPolicyError(err.message || "Unable to load policy document");
    } finally {
      setPolicyLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab === "database" && !dbData && !dbLoading) {
      loadDatabase();
    }
    if (activeTab === "policies" && !policyContent && !policyLoading) {
      loadPolicies();
    }
  }, [activeTab, dbData, dbLoading, policyContent, policyLoading]);

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

      <div className="tabs">
        {[
          { id: "agent", label: "Agent" },
          { id: "database", label: "Database data" },
          { id: "policies", label: "Policies" },
        ].map((tab) => (
          <button
            key={tab.id}
            className={`tab ${activeTab === tab.id ? "active" : ""}`}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === "agent" && (
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
      )}

      {activeTab === "database" && (
        <DatabaseView data={dbData} loading={dbLoading} error={dbError} onRefresh={loadDatabase} />
      )}

      {activeTab === "policies" && (
        <PolicyView
          content={policyContent}
          loading={policyLoading}
          error={policyError}
          onRefresh={loadPolicies}
        />
      )}
    </div>
  );
}

function DatabaseView({ data, loading, error, onRefresh }) {
  const tables = data?.tables || [];
  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Data Explorer</p>
          <h2>Snapshot of every table</h2>
          <p className="subhead">Pulled directly from SQLite (limited to the first 200 rows).</p>
        </div>
        <div className="panel-actions">
          <button className="ghost" onClick={onRefresh} disabled={loading}>
            {loading ? "Refreshing..." : "Refresh"}
          </button>
        </div>
      </div>

      {loading && <p className="muted">Loading database snapshot...</p>}
      {error && <div className="error">{error}</div>}
      {!loading && !error && tables.length === 0 && <p className="muted">No tables found.</p>}

      <div className="table-grid">
        {tables.map((table) => (
          <div className="table-card" key={table.name}>
            <div className="table-card-header">
              <div>
                <p className="eyebrow">Table</p>
                <h3>{table.name}</h3>
              </div>
              <div className="pill subtle">{table.rows?.length || 0} rows</div>
            </div>
            <ResultTable result={{ columns: table.columns, rows: table.rows }} />
          </div>
        ))}
      </div>
    </section>
  );
}

function PolicyView({ content, loading, error, onRefresh }) {
  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Policy Source</p>
          <h2>Markdown rules</h2>
          <p className="subhead">The exact policy document used for grounding the agent.</p>
        </div>
        <div className="panel-actions">
          <button className="ghost" onClick={onRefresh} disabled={loading}>
            {loading ? "Refreshing..." : "Reload"}
          </button>
        </div>
      </div>

      {loading && <p className="muted">Loading policy document...</p>}
      {error && <div className="error">{error}</div>}
      {!loading && !error && !content && <p className="muted">Policy document is empty.</p>}

      {content && (
        <article className="policy-card">
          <pre className="policy-text">{content}</pre>
        </article>
      )}
    </section>
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
