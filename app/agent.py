from __future__ import annotations

from typing import Any, Dict

from app.docs_loader import DocsLoader
from app.llm import LLMClient, LLMUnavailableError
from app.logger import TraceLogger
from app.router import Router
from app.sql_executor import PIIBlockError, SQLExecutor


class Agent:
    def __init__(
        self,
        db_path: str = "data/store.db",
        log_path: str = "logs/trace.jsonl",
        logger: TraceLogger | None = None,
        record_events: bool = False,
    ) -> None:
        self.logger = logger or TraceLogger(log_path=log_path, record_events=record_events)
        self.llm = LLMClient(logger=self.logger)
        self.router = Router(self.llm, self.logger)
        self.docs = DocsLoader()
        self.sql = SQLExecutor(db_path, self.llm, self.logger)

    def handle(self, query: str) -> Dict[str, Any]:
        try:
            self.logger.log("agent_handle_start", query=query)
            pii_terms = self._detect_pii_terms(query)
            if pii_terms:
                raise PIIBlockError("Raw PII requested; request blocked.", pii_terms)

            route_info = self.router.route(query)
            decision = str(route_info.get("decision") or "docs")

            if route_info.get("unknown"):
                return {"message": "I couldn't understand that request. Please rephrase or ask a specific question."}
            if decision == "docs":
                return self._handle_docs_case(query)
            if decision == "hybrid":
                return self._handle_hybrid_case(query)
            return self._handle_sql_case(query)
        except PIIBlockError as exc:
            self.logger.log(
                "pii_block_result",
                query=query,
                blocked=True,
                fields=exc.fields,
                reason=str(exc),
            )
            return {
                "error": str(exc),
                "pii_fields": exc.fields,
                "message": (
                    "I'm sorry, I cannot share customer PII. "
                    "I can provide aggregated or de-identified results instead."
                ),
            }
        except LLMUnavailableError as exc:
            self.logger.log("llm_unavailable", message=str(exc))
            return {"message": str(exc)}

    def _detect_pii_terms(self, query: str) -> list[str]:
        lowered = query.lower()
        return [term for term in ["email", "phone", "address", "pii"] if term in lowered]

    def _handle_docs_case(self, query: str) -> Dict[str, Any]:
        context = self._retrieve_policy_context(query, stage="doc1_policy_retrieval_result")
        answer = self.llm.answer_from_docs(query, context)
        self.logger.log(
            "doc_final_answer_result",
            mode="docs",
            query=query,
            has_context=bool(context.strip()),
            context_chars=len(context),
        )
        return {"message": answer}

    def _handle_sql_case(self, query: str) -> Dict[str, Any]:
        schema = self.sql.schema_summary()
        sql = self._generate_sql(
            query,
            schema=schema,
            stage="sql1_generation_result",
        )
        result = self._run_sql_pipeline(sql, schema=schema, query=query)
        self.logger.log(
            "sql_final_answer_result",
            mode="sql",
            query=query,
            rows=len(result.get("rows", [])) if isinstance(result, dict) else 0,
            error=result.get("error") if isinstance(result, dict) else None,
        )
        return {"result": result}

    def _handle_hybrid_case(self, query: str) -> Dict[str, Any]:
        policy_context = self._retrieve_policy_context(query, stage="h1_policy_extraction_result")
        self.logger.log(
            "h1_policy_answer_result",
            query=query,
            has_context=bool(policy_context.strip()),
            answer_preview=policy_context.strip()[:200],
        )
        schema = self.sql.schema_summary()
        sql = self._generate_sql(
            query,
            schema=schema,
            business_rule=policy_context,
            stage="h2_sql_generation_result",
        )
        result = self._run_sql_pipeline(sql, schema=schema, query=query)
        self.logger.log(
            "h5_final_answer_result",
            mode="hybrid",
            query=query,
            rows=len(result.get("rows", [])) if isinstance(result, dict) else 0,
            error=result.get("error") if isinstance(result, dict) else None,
        )
        return {"result": result}

    def _retrieve_policy_context(self, query: str, stage: str) -> str:
        full_context = self.docs.extract_rule(query)
        selected = self.llm.select_policy_context(query, full_context, fallback=full_context)
        self.logger.log(
            stage,
            characters=len(selected),
            has_context=bool(selected.strip()),
            full_context_chars=len(full_context),
        )
        return selected

    def _generate_sql(self, query: str, *, schema: str, business_rule: str = "", stage: str) -> str:
        sql = self.llm.generate_sql(query, business_rule=business_rule, schema=schema)
        self.logger.log(
            stage,
            business_rule=business_rule,
            sql_preview=sql.strip()[:200],
        )
        return sql

    def _run_sql_pipeline(self, sql: str, *, schema: str, query: str) -> Dict[str, Any]:
        sql_preview = sql.strip()[:200]
        self.logger.log(
            "sql2_self_correction_sql_execution_loop_start",
            query=query,
            max_attempts=3,
            sql_preview=sql_preview,
            schema_chars=len(schema),
        )
        result = self.sql.execute_with_retry(sql, schema=schema)
        rows = result.get("rows") if isinstance(result, dict) else None
        status = "success" if rows is not None else "error"
        self.logger.log(
            "sql3_sqlite_execution_result",
            query=query,
            status=status,
            rows=len(rows) if rows else 0,
            error=result.get("error") if isinstance(result, dict) else None,
        )
        return result
