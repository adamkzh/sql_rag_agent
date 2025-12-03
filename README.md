Resilient Multi-Tool Agent (Text-to-SQL + Policy RAG)
======================================================

What it does
------------
- Routes queries between SQL, docs, and hybrid modes using LLM function-calling logic.
- Generates SQLite-safe SQL with a retry-and-correct loop.
- Retrieves policy snippets from `data/policies.md` for business-rule alignment.
- Masks PII (email, phone, address) before returning results.
- Emits JSONL trace logs for each step to `logs/trace.jsonl`.

Routing pipeline
----------------
1. User query → optional normalization.
2. Policy-term rule check (deterministic fast-path).
3. LLM-based boolean router decides `requires_sql` / `requires_policy`.
4. Final routing decision fan-outs into three deterministic pipelines:
   - **Case 1 — SQL only**: `[SQL1]` SQL generation → `[SQL2]` self-correction loop (max 3) → `[SQL3]` SQLite execution → `[SQL4]` PII guardrail filter → final answer.
   - **Case 2 — Docs only**: `[DOC1]` retrieve policy context from `data/policies.md` → final answer.
   - **Case 3 — Hybrid**: `[H1]` policy extraction → `[H2]` policy-injected SQL generation → `[H3]` self-correction loop → `[H4]` SQLite execution → `[H5]` PII guardrail filter → final answer.
5. Every stage emits a structured trace log so you can audit decisions end-to-end.

Project layout
--------------
- `app/agent.py` — orchestrates routing, SQL/doc handling, PII guardrail.
- `app/router.py` — classifies queries (sql/docs/hybrid).
- `app/docs_loader.py` — loads and searches policy docs.
- `app/sql_executor.py` — SQLite executor with retry + LLM correction.
- `app/pii.py` — PII detection and masking helpers.
- `app/llm.py` — OpenAI wrapper with offline fallbacks.
- `app/logger.py` — structured JSON logging.
- `data/store.db` — sample SQLite database (customers + orders).
- `data/policies.md` — example business rules.
- `main.py` — CLI entry point.
- `requirements.txt` — dependencies (OpenAI SDK).

Setup
-----
1) Install dependencies:
```
pip install -r requirements.txt
```
2) (Optional) Set your key for live LLM calls:
```
export OPENAI_API_KEY=sk-...
```
Without a key, the agent uses heuristic fallbacks for routing and SQL generation.

Run the CLI demo
----------------
```
python main.py "List VIP customers"
```
Or interactively:
```
python main.py
Enter a query: show orders per customer
```

HTTP API + React UI
-------------------
Backend (FastAPI):
```
uvicorn server:app --reload --port 8000
```

Frontend (React/Vite):
```
cd ui
npm install   # first time only
npm run dev
```
The UI expects the API at `http://localhost:8000`. Override with `VITE_API_URL` if needed.

PII guardrails
--------------
- Requests for raw `email`, `phone`, or `address` are rejected with a safe message.
- Any result set containing those fields is masked before returning.

Logs
----
- JSONL traces are written to `logs/trace.jsonl`. Each line includes `step`, timestamps, and context.

Notes
-----
- The sample DB is small and intended for local testing; swap `data/store.db` with your dataset as needed.
- Only SELECT statements are executed; destructive SQL is blocked.
