from __future__ import annotations

from app.logger import TraceLogger


class PolicyRouter:
    def __init__(self, policy_terms: list[str], logger: TraceLogger | None = None) -> None:
        self.policy_terms = [term.lower() for term in policy_terms]
        self.logger = logger

    def detect(self, query: str) -> bool:
        lowered = query.lower()
        hit = any(term in lowered for term in self.policy_terms)
        if self.logger:
            self.logger.log("policy_router_result", policy_keyword_hit=hit)
        return hit
