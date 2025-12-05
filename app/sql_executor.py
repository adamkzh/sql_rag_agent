from __future__ import annotations

import sqlite3
from typing import Any, Dict, List, Tuple

from app.llm import LLMClient
from app.logger import TraceLogger
from app.pii import PII_FIELDS


class PIIBlockError(Exception):
    def __init__(self, message: str, fields: list[str]) -> None:
        super().__init__(message)
        self.fields = fields


class SQLExecutor:
    def __init__(self, db_path: str, llm: LLMClient, logger: TraceLogger) -> None:
        self.db_path = db_path
        self.llm = llm
        self.logger = logger
        self._schema_cache: str | None = None

    def _is_safe(self, sql: str) -> bool:
        lowered = sql.lower().strip()
        is_select = lowered.startswith("select")
        if self.logger:
            self.logger.log("sql_guardrail_check_result", sql_preview=sql[:200], allowed=is_select)
        return is_select

    def _run_sql(self, sql: str) -> Tuple[List[str], List[Dict[str, Any]]]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.execute(sql)
            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            data = [dict(row) for row in rows]
            return columns, data
        finally:
            conn.close()

    def execute_with_retry(self, sql: str, max_attempts: int = 3, schema: str = "") -> Dict[str, Any]:
        """Execute a SELECT with safety checks, retries, and PII masking."""
        original_sql = sql
        attempts: List[Dict[str, Any]] = []
        schema_text = schema or self.schema_summary()
        for attempt in range(1, max_attempts + 1):
            sql = self._extract_sql(sql)
            if not self._is_safe(sql):
                msg = "Blocked non-SELECT statement"
                self.logger.log("sql_execute", attempt=attempt, status="blocked", message=msg)
                return {"error": msg, "attempts": attempts}
            try:
                columns, data = self._run_sql(sql)
                masked_data = self._mask_rows(columns, data)
                if not masked_data:
                    attempts.append({"attempt": attempt, "error": "Empty result set"})
                    self.logger.log("sql_execute", attempt=attempt, status="empty", rows=0)
                    if attempt == max_attempts:
                        return {
                            "columns": columns,
                            "rows": masked_data,
                            "attempts": attempts,
                            "warning": "Empty result set",
                        }
                    sql = self.llm.correct_sql(
                        sql,
                        "Query returned zero rows; please regenerate the SQL based on the schema and policy context to return correct results.",
                        schema=schema_text,
                    )
                    self.logger.log(
                        "sql_retry_empty",
                        attempt=attempt + 1,
                        previous_attempt=attempt,
                        sql=sql,
                        cause="empty_result",
                    )
                    continue
                self.logger.log("sql_execute", attempt=attempt, status="success", rows=len(masked_data))
                return {"columns": columns, "rows": masked_data, "attempts": attempts}
            except PIIBlockError as exc:
                attempts.append({"attempt": attempt, "error": str(exc), "pii_fields": exc.fields})
                self.logger.log(
                    "sql_execute",
                    attempt=attempt,
                    status="blocked_pii",
                    error=str(exc),
                    fields=exc.fields,
                )
                return {"error": str(exc), "pii_fields": exc.fields, "attempts": attempts}
            except Exception as exc:  # sqlite errors are informative
                err_msg = str(exc)
                attempts.append({"attempt": attempt, "error": err_msg})
                self.logger.log("sql_execute", attempt=attempt, status="error", error=err_msg)
                lower_err = err_msg.lower()
                if "no such table" in lower_err:
                    return {
                        "error": err_msg,
                        "attempts": attempts,
                        "schema": schema_text,
                    }
                if attempt == max_attempts:
                    break
                sql = self.llm.correct_sql(sql, err_msg, schema=schema_text)
                self.logger.log(
                    "sql_retry",
                    attempt=attempt + 1,
                    previous_attempt=attempt,
                    sql=sql,
                    cause=err_msg,
                )
        return {"error": f"Failed after {max_attempts} attempts", "attempts": attempts, "sql": original_sql}

    def schema_summary(self) -> str:
        """Return cached schema description for prompting."""
        if self._schema_cache is not None:
            return self._schema_cache
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
            tables = [row[0] for row in cursor.fetchall()]
            summaries: List[str] = []
            for table in tables:
                cols_cursor = conn.execute(f"PRAGMA table_info('{table}')")
                cols = [f"{c[1]} {c[2]}" for c in cols_cursor.fetchall()]
                summaries.append(f"Table {table} ({', '.join(cols)})")
            self._schema_cache = "\n".join(summaries)
            return self._schema_cache
        finally:
            conn.close()

    def _extract_sql(self, sql: str) -> str:
        """Strip markdown/prose and return the SQL statement."""
        import re

        # Pull from fenced code block first.
        fenced = re.search(r"```(?:sql)?\s*(.*?)```", sql, flags=re.IGNORECASE | re.DOTALL)
        if fenced:
            sql = fenced.group(1)

        sql = sql.strip()
        match = re.search(r"select\b", sql, flags=re.IGNORECASE)
        if match:
            return sql[match.start():].strip()
        return sql

    def _mask_rows(self, columns: List[str], rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        pii_columns = [col for col in columns if col.lower() in PII_FIELDS]
        if not pii_columns:
            self.logger.log(
                "sql4_pii_guardrail_result",
                applied=False,
                rows=len(rows),
            )
            return rows
        self.logger.log(
            "sql4_pii_guardrail_result",
            applied=True,
            fields=pii_columns,
            rows=len(rows),
        )
        raise PIIBlockError("Query includes PII columns; request blocked.", pii_columns)
