from __future__ import annotations

from typing import Any, Dict

from app.docs_loader import DocsLoader
from app.llm import LLMClient
from app.logger import TraceLogger
from app.router import Router
from app.sql_executor import SQLExecutor


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
        if self._is_pii_request(query):
            self.logger.log("pii", blocked=True, reason="raw PII requested")
            return {
                "message": (
                    "I'm sorry, I cannot share customer PII. "
                    "I can provide aggregated or de-identified results instead."
                )
            }

        route_info = self.router.route(query)
        decision = str(route_info.get("decision") or "docs")
        self.logger.log(
            "stage_case_selection",
            decision=decision,
            requires_sql=bool(route_info.get("requires_sql")),
            requires_policy=bool(route_info.get("requires_policy")),
            unknown=bool(route_info.get("unknown")),
        )

        if route_info.get("unknown"):
            return {"message": "I couldn't understand that request. Please rephrase or ask a specific question."}
        if decision == "docs":
            return self._handle_docs_case(query)
        if decision == "hybrid":
            return self._handle_hybrid_case(query)
        return self._handle_sql_case(query)

    def _is_pii_request(self, query: str) -> bool:
        lowered = query.lower()
        return any(term in lowered for term in ["email", "phone", "address", "pii"])

    def _handle_docs_case(self, query: str) -> Dict[str, Any]:
        context = self._retrieve_policy_context(query, stage="stage_doc1_policy_retrieval")
        answer = self.llm.answer_from_docs(query, context)
        self.logger.log("stage_doc_final_answer", mode="docs", has_context=bool(context.strip()))
        return {"message": answer}

    def _handle_sql_case(self, query: str) -> Dict[str, Any]:
        schema = self.sql.schema_summary()
        sql = self._generate_sql(
            query,
            schema=schema,
            stage="stage_sql1_generation",
        )
        result = self._run_sql_pipeline(sql, schema=schema)
        self.logger.log("stage_sql_final_answer", mode="sql")
        return {"result": result}

    def _handle_hybrid_case(self, query: str) -> Dict[str, Any]:
        policy_context = self._retrieve_policy_context(query, stage="stage_h1_policy_extraction")
        self.logger.log(
            "stage_h1_policy_answer",
            query=query,
            has_context=bool(policy_context.strip()),
            answer_preview=policy_context.strip()[:200],
        )
        schema = self.sql.schema_summary()
        sql = self._generate_sql(
            query,
            schema=schema,
            business_rule=policy_context,
            stage="stage_h2_sql_generation",
        )
        result = self._run_sql_pipeline(sql, schema=schema)
        self.logger.log("stage_h5_final_answer", mode="hybrid")
        return {"result": result}

    def _retrieve_policy_context(self, query: str, stage: str) -> str:
        context = self.docs.extract_rule(query)
        self.logger.log(
            stage,
            characters=len(context),
            has_context=bool(context.strip()),
        )
        return context

    def _generate_sql(self, query: str, *, schema: str, business_rule: str = "", stage: str) -> str:
        sql = self.llm.generate_sql(query, business_rule=business_rule, schema=schema)
        self.logger.log(
            stage,
            business_rule=business_rule,
            sql_preview=sql.strip()[:200],
        )
        return sql

    def _run_sql_pipeline(self, sql: str, *, schema: str) -> Dict[str, Any]:
        self.logger.log("stage_sql2_self_correction_loop", max_attempts=3)
        result = self.sql.execute_with_retry(sql, schema=schema)
        print(result)
        rows = result.get("rows") if isinstance(result, dict) else None
        status = "success" if rows is not None else "error"
        self.logger.log(
            "stage_sql3_sqlite_execution",
            status=status,
            rows=len(rows) if rows else 0,
            error=result.get("error") if isinstance(result, dict) else None,
        )
        return result
