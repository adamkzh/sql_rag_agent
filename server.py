import sqlite3
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.agent import Agent
from app.logger import TraceLogger


app = FastAPI(title="Resilient Multi-Tool Agent API")
DB_PATH = Path("data/store.db")
POLICY_PATH = Path("data/policies.md")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class QueryRequest(BaseModel):
    query: str


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/query")
async def run_query(payload: QueryRequest) -> dict:
    logger = TraceLogger(record_events=True)
    agent = Agent(logger=logger, record_events=True)
    response = agent.handle(payload.query)
    return {"response": response, "trace": logger.events()}


@app.get("/database")
async def database_dump(limit: int = Query(200, ge=1, le=1000)) -> dict:
    if not DB_PATH.exists():
        raise HTTPException(status_code=404, detail="Database not found")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        tables = [
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        ]
        table_payload = []
        for table in tables:
            columns = [row[1] for row in conn.execute(f"PRAGMA table_info('{table}')").fetchall()]
            rows = conn.execute(f"SELECT * FROM '{table}' LIMIT ?", (limit,)).fetchall()
            table_payload.append(
                {
                    "name": table,
                    "columns": columns,
                    "rows": [dict(row) for row in rows],
                }
            )
        return {"tables": table_payload, "row_limit": limit, "table_count": len(table_payload)}
    finally:
        conn.close()


@app.get("/policies")
async def get_policies() -> dict:
    if not POLICY_PATH.exists():
        raise HTTPException(status_code=404, detail="Policy file not found")
    return {"content": POLICY_PATH.read_text(encoding="utf-8")}
