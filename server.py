from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.agent import Agent
from app.logger import TraceLogger


app = FastAPI(title="Resilient Multi-Tool Agent API")

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
