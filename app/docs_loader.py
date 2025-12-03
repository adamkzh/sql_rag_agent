from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List

from app.utils import keyword_match


@dataclass
class PolicyDoc:
    content: str

    def search(self, query: str, top_k: int = 3) -> List[str]:
        """Return the entire document; LLM will decide relevance."""
        return [self.content]


class DocsLoader:
    def __init__(self, path: str = "data/policies.md") -> None:
        self.path = Path(path)
        self.doc = PolicyDoc(self._load())

    def _load(self) -> str:
        if not self.path.exists():
            return ""
        return self.path.read_text(encoding="utf-8")

    def extract_rule(self, question: str) -> str:
        return self.doc.content
