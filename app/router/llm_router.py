from __future__ import annotations

from typing import Any, Dict

from app.llm import LLMClient
from app.logger import TraceLogger


class LLMRouter:
    def __init__(self, llm: LLMClient, logger: TraceLogger | None = None) -> None:
        self.llm = llm
        self.logger = logger

    def classify(self, query: str) -> Dict[str, Any]:
        tools = self.llm.classify_tools(query, skip_policy_rule=True)
        if self.logger:
            self.logger.log("llm_router_result", **tools)
        return tools
