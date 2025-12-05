from __future__ import annotations

from typing import Dict, Optional

from app.logger import TraceLogger


class EmbeddingRouter:
    """
    Placeholder embedding-based router.
    Returns None until an embedding model/store is wired in.
    """

    def __init__(self, logger: TraceLogger | None = None) -> None:
        self.logger = logger

    def suggest(self, query: str) -> Optional[Dict[str, str | bool]]:
        """
        Optionally return a suggestion like {"decision": "docs", "reason": "..."}.
        Currently returns None to keep routing LLM-driven until embeddings are added.
        """
        if self.logger:
            self.logger.log("embedding_router_result", used=False, decision=None)
        return None
