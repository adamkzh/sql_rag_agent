from __future__ import annotations

from typing import Dict

from app.llm import LLMClient
from app.logger import TraceLogger
from app.router.embedding_router import EmbeddingRouter
from app.router.llm_router import LLMRouter
from app.router.policy_router import PolicyRouter
from app.router.pre_router import PreRouter


class Router:
    """Multi-layer routing: preprocess → policy keyword → embedding hint → LLM classifier."""

    def __init__(self, llm: LLMClient, logger: TraceLogger) -> None:
        self.llm = llm
        self.logger = logger
        self.pre_router = PreRouter(logger)
        self.embedding_router = EmbeddingRouter(logger)
        self.policy_router = PolicyRouter(llm.policy_terms, logger)
        self.llm_router = LLMRouter(llm, logger)

    def route(self, query: str) -> Dict[str, str | bool | None]:
        normalized = self.pre_router.normalize(query)

        policy_hit = self.policy_router.detect(normalized)
        embedding_hint = self.embedding_router.suggest(normalized)
        llm_tools = self.llm_router.classify(normalized)

        requires_policy = policy_hit or bool(llm_tools.get("requires_policy", False))
        requires_sql = bool(llm_tools.get("requires_sql", False))
        unknown = bool(llm_tools.get("unknown", False))

        if embedding_hint:
            decision_hint = str(embedding_hint.get("decision") or "").lower()
            if decision_hint == "docs":
                requires_policy = True
                requires_sql = False
            elif decision_hint == "sql":
                requires_sql = True
            elif decision_hint == "hybrid":
                requires_policy = True
                requires_sql = True

        decision = self._infer_decision(requires_sql, requires_policy, unknown)
        payload: Dict[str, str | bool | None] = {
            "normalized_query": normalized,
            "requires_sql": requires_sql,
            "requires_policy": requires_policy,
            "unknown": unknown,
            "decision": decision,
            "source": str(llm_tools.get("source", "router")),
            "explanation": str(llm_tools.get("explanation", "")),
            "policy_keyword_hit": policy_hit,
            "embedding_decision": embedding_hint.get("decision") if embedding_hint else None,
        }
        self.logger.log("final_router_result", **payload)
        return payload

    def _infer_decision(self, requires_sql: bool, requires_policy: bool, unknown: bool) -> str:
        if unknown:
            return "unknown"
        if requires_sql and requires_policy:
            return "hybrid"
        if requires_policy:
            return "docs"
        if requires_sql:
            return "sql"
        return "docs"
