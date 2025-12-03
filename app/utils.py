from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Iterable, List


def is_recent(date_str: str, window_days: int = 365) -> bool:
    """Return True if the provided ISO date string is within the window."""
    try:
        dt = datetime.fromisoformat(date_str)
    except ValueError:
        return False
    return datetime.utcnow() - dt <= timedelta(days=window_days)


def keyword_match(text: str, keywords: Iterable[str]) -> bool:
    pattern = "|".join(re.escape(k.lower()) for k in keywords)
    return re.search(pattern, text.lower()) is not None if pattern else False


def dedent_lines(lines: List[str]) -> str:
    return "\n".join(line.strip() for line in lines if line.strip())
