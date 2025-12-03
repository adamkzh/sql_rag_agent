from __future__ import annotations

from typing import Dict

from app.llm import LLMClient
from app.logger import TraceLogger


class Router:
    """Deterministic + LLM routing pipeline."""

    def __init__(self, llm: LLMClient, logger: TraceLogger) -> None:
        self.llm = llm
        self.logger = logger

    def route(self, query: str) -> Dict[str, str | bool]:
        normalized = self._preprocess(query)
        self.logger.log("query_preprocess", original=query, normalized=normalized)

        tools = self.llm.classify_tools(normalized)
        self.logger.log("stage_llm_router", **tools)
        return self._finalize_decision(normalized, tools)

    def _preprocess(self, query: str) -> str:
        """Basic normalization for deterministic stage."""
        return " ".join(query.strip().split())

    def _finalize_decision(self, normalized_query: str, tools: Dict[str, str | bool]) -> Dict[str, str | bool]:
        decision = str(tools.get("decision"))
        payload: Dict[str, str | bool] = {
            "normalized_query": normalized_query,
            "requires_sql": bool(tools.get("requires_sql", False)),
            "requires_policy": bool(tools.get("requires_policy", False)),
            "decision": decision if decision != "None" else self._infer_decision(tools),
            "source": str(tools.get("source", "router")),
            "explanation": str(tools.get("explanation", "")),
        }
        self.logger.log("stage_final_route", **payload)
        return payload

    def _infer_decision(self, tools: Dict[str, str | bool]) -> str:
        requires_sql = bool(tools.get("requires_sql", False))
        requires_policy = bool(tools.get("requires_policy", False))
        if requires_sql and requires_policy:
            return "hybrid"
        if requires_policy:
            return "docs"
        if requires_sql:
            return "sql"
        return "docs"
