import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class TraceLogger:
    """Structured logger that emits JSON lines for each agent step."""

    def __init__(self, log_path: Optional[str] = None, record_events: bool = False) -> None:
        self.log_path = Path(log_path) if log_path else None
        self.record_events = record_events
        self._events: List[Dict[str, Any]] = []
        self._setup_text_logger()
        if self.log_path:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def _setup_text_logger(self) -> None:
        logging.basicConfig(
            level=logging.INFO,
            format="%(message)s",
        )
        self.text_logger = logging.getLogger("agent")

    def log(self, step: str, **payload: Any) -> None:
        event: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "step": step,
        }
        event.update(payload)
        line = json.dumps(event)
        self.text_logger.info(line)
        if self.record_events:
            self._events.append(event)
        if self.log_path:
            with self.log_path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")

    def events(self) -> List[Dict[str, Any]]:
        return list(self._events)


def get_logger(log_path: Optional[str] = None) -> TraceLogger:
    return TraceLogger(log_path=log_path)
