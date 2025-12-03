from __future__ import annotations

import os
import json
from dataclasses import dataclass
from typing import Any, Dict, Optional

from app.logger import TraceLogger
from app.utils import keyword_match

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None  # type: ignore


SYSTEM_ROUTER_PROMPT = """
You are a tool routing classifier.
Determine whether the user query requires database SQL, business policy lookup, or both.
If the query is nonsense, empty, or unrelated, mark it as unknown.

Definitions:
- SQL: direct DB queries, counts, sums, joins, filters.
- Policy: business rules defined in policies.md (VIP rules, return rules, restocking fee, shipping rules)
- Unknown: junk/unrelated/empty input; do not route to SQL or policy.

Output ONLY a function call with:
{
   "requires_sql": true/false,
   "requires_policy": true/false,
   "unknown": true/false,
   "explanation": "brief reasoning"
}
""".strip()

CLASSIFY_SCHEMA = {
    "type": "object",
    "properties": {
        "requires_sql": {"type": "boolean"},
        "requires_policy": {"type": "boolean"},
        "explanation": {"type": "string"},
        "unknown": {"type": "boolean"},
    },
    "required": ["requires_sql", "requires_policy"],
}


@dataclass
class Classification:
    requires_sql: bool
    requires_policy: bool
    explanation: str = ""
    source: str = "heuristic"
    unknown: bool = False

    @property
    def decision(self) -> str:
        if self.unknown:
            return "unknown"
        if self.requires_sql and self.requires_policy:
            return "hybrid"
        if self.requires_policy:
            return "docs"
        if self.requires_sql:
            return "sql"
        return "docs"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "requires_sql": self.requires_sql,
            "requires_policy": self.requires_policy,
            "explanation": self.explanation,
            "decision": self.decision,
            "source": self.source,
            "unknown": self.unknown,
        }


def _has_key() -> bool:
    return bool(os.getenv("OPENAI_API_KEY")) and OpenAI is not None


class LLMClient:
    def __init__(self, model: str = "gpt-4o-mini", logger: TraceLogger | None = None) -> None:
        self.model = model
        self.available = _has_key()
        self.client = OpenAI() if self.available else None
        self.logger = logger
        self.policy_terms = [
            "policy",
            "rule",
            "guideline",
            "vip",
            "refund",
            "return",
            "shipping",
            "restocking",
        ]

    def _chat(self, messages: Any, tools: Optional[list] = None) -> Dict[str, Any]:
        if not self.client:
            raise RuntimeError("OpenAI client unavailable")
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
        )
        return response.to_dict()

    # Router
    def classify_query(self, query: str) -> str:
        """Return sql/docs/hybrid decision (logs inside classify_tools)."""
        tools = self.classify_tools(query)
        return tools["decision"]

    def classify_tools(self, query: str, *, skip_policy_rule: bool = False) -> Dict[str, Any]:
        """
        Final classification logic:
        - policy keyword hit → requires_policy = True (NOT SQL!)
        - LLM decides requires_sql / requires_policy
        - Final routing merges both

        This avoids mistakes like:
        "Give me the VIP definition" → docs (correct)
        "List VIP customers" → hybrid (correct)
        """

        # Step 1 — keyword-based detection (only affects requires_policy)
        keyword_policy = False
        if not skip_policy_rule:
            keyword_policy = self._policy_keyword_hit(query)  # e.g., "VIP", "return", "restocking"

        # Step 2 — LLM judgment (boolean router)
        if self.available:
            llm_cls = self._classify_via_llm(query)
        else:
            llm_cls = self._heuristic_classification(query)

        # Step 3 — Merge logic (MOST IMPORTANT PART)

        # Do NOT infer SQL from keyword hits!
        # Policy keywords only imply requires_policy.
        merged_requires_policy = keyword_policy or llm_cls.requires_policy

        # SQL requirement ALWAYS comes from LLM (never from keyword)
        merged_requires_sql = llm_cls.requires_sql

        # Step 4 — Final decision
        final = Classification(
            requires_sql=merged_requires_sql,
            requires_policy=merged_requires_policy,
            explanation=llm_cls.explanation,
            source="merged",
            unknown=llm_cls.unknown,
        )

        return self._log_classification(query, final)


    def extract_business_rule(self, question: str, fallback: str = "") -> str:
        if not self.available:
            return fallback
        messages = [
            {"role": "system", "content": "Extract business rules relevant to the question."},
            {"role": "user", "content": question},
        ]
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
        )
        return resp.choices[0].message.content or fallback

    def generate_sql(self, query: str, business_rule: str = "", schema: str = "") -> str:
        if not self.available:
            return self._heuristic_sql(query, business_rule)
        system = (
            "You are a SQLite expert. Generate safe SELECT-only SQL. "
            "Return only the SQL statement with no explanation. "
            "Never include raw email, phone, or address unless needed for joins; prefer aggregated or masked data. "
            "When a business rule is provided, you must encode every constraint from that rule into the SQL "
            "(e.g., VIP definition thresholds, date windows, spend minimums). "
            "Do not drop rule constraints even if the user query omits them. "
            "Use only the tables and columns listed in the provided schema. "
            "If the request cannot be satisfied with the available tables, return a harmless placeholder query like "
            "SELECT 'no matching table' AS message;"
        )
        if schema:
            system += f"\nDatabase schema:\n{schema}"
        messages = [
            {"role": "system", "content": system},
            {
            "role": "user",
            "content": f"User query: {query}\nBusiness rule (must be enforced): {business_rule}",
            },
        ]
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
        )
        raw = resp.choices[0].message.content or ""
        return self._extract_sql(raw)

    def correct_sql(self, original_sql: str, error_message: str, schema: str = "") -> str:
        if not self.available:
            return original_sql
        system = (
            "You are helping fix a SQLite query. Return only corrected SQL. "
            "Do not include explanations. "
            "Use only the tables/columns in the provided schema; if the requested table does not exist, "
            "return a safe placeholder like SELECT 'no matching table' AS message;"
        )
        if schema:
            system += f"\nDatabase schema:\n{schema}"
        messages = [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": f"Original SQL:\n{original_sql}\n\nError:\n{error_message}",
            },
        ]
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
        )
        return resp.choices[0].message.content or original_sql

    def _heuristic_sql(self, query: str, business_rule: str) -> str:
        # Extremely simple heuristic for offline/demo use.
        rule_text = business_rule.lower()
        if "vip" in rule_text:
            return """
            SELECT c.name, c.email, c.phone, c.address, SUM(o.amount) AS total_spent
            FROM customers c
            JOIN orders o ON o.customer_id = c.id
            WHERE o.order_date >= date('now','-12 months')
            GROUP BY c.id
            HAVING total_spent > 1000
            ORDER BY total_spent DESC;
            """
        if keyword_match(query, ["vip", "VIP"]):
            return """
            SELECT c.name, c.email, c.phone, c.address, SUM(o.amount) AS total_spent
            FROM customers c
            JOIN orders o ON o.customer_id = c.id
            WHERE o.order_date >= date('now','-12 months')
            GROUP BY c.id
            HAVING total_spent > 1000
            ORDER BY total_spent DESC;
            """
        if keyword_match(query, ["orders", "spend", "revenue"]):
            return """
            SELECT c.name, SUM(o.amount) AS total_spent, COUNT(o.id) AS order_count
            FROM customers c
            JOIN orders o ON o.customer_id = c.id
            GROUP BY c.id
            ORDER BY total_spent DESC;
            """
        return "SELECT * FROM customers LIMIT 5;"

    def answer_from_docs(self, question: str, context: str) -> str:
        """Answer using provided policy context only."""
        if not context.strip():
            return "No relevant policy found."
        if not self.available:
            return context
        system = (
            "You are a compliance/policy assistant. Answer the question strictly using the provided policy snippets. "
            "If the policy does not contain the answer, say you do not have that information."
        )
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": f"Policy snippets:\n{context}\n\nQuestion: {question}"},
        ]
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
        )
        return resp.choices[0].message.content or context

    def _extract_sql(self, text: str) -> str:
        """Strip markdown/prose and keep the SQL statement."""
        import re

        fenced = re.search(r"```(?:sql)?\s*(.*?)```", text, flags=re.IGNORECASE | re.DOTALL)
        if fenced:
            text = fenced.group(1)

        text = text.strip()
        match = re.search(r"select\b", text, flags=re.IGNORECASE)
        if match:
            return text[match.start():].strip()
        return text

    def _policy_keyword_hit(self, query: str) -> bool:
        return any(term in query.lower() for term in self.policy_terms)

    def _classify_via_llm(self, query: str) -> Classification:
        tools_spec = [
            {
                "type": "function",
                "function": {
                    "name": "classify_query",
                    "parameters": CLASSIFY_SCHEMA,
                },
            }
        ]
        messages = [
            {"role": "system", "content": SYSTEM_ROUTER_PROMPT},
            {"role": "user", "content": query},
        ]

        requires_sql = True
        requires_policy = False
        explanation = ""
        unknown = False

        resp = self._chat(messages, tools=tools_spec)
        tool_calls = resp["choices"][0]["message"].get("tool_calls", [])
        if tool_calls:
            args = tool_calls[0]["function"].get("arguments", "{}")
            try:
                payload = json.loads(args)
                requires_sql = bool(payload.get("requires_sql", True))
                requires_policy = bool(payload.get("requires_policy", False))
                explanation = payload.get("explanation", "")
                unknown = bool(payload.get("unknown", False))
            except (json.JSONDecodeError, TypeError, ValueError):
                unknown = False

        return Classification(
            requires_sql=requires_sql,
            requires_policy=requires_policy,
            explanation=explanation,
            source="llm",
            unknown=unknown,
        )

    def _heuristic_classification(self, query: str) -> Classification:
        if self._is_nonsense(query):
            return Classification(
                requires_sql=False,
                requires_policy=False,
                source="heuristic",
                explanation="Query is empty or not understandable.",
                unknown=True,
            )
        requires_policy = keyword_match(query, ["policy", "rule", "guideline"])
        requires_sql = not requires_policy or keyword_match(
            query, ["count", "list", "sum", "order", "customer", "product", "revenue", "amount"]
        )
        return Classification(
            requires_sql=requires_sql,
            requires_policy=requires_policy,
            source="heuristic",
            unknown=False,
        )

    def _is_nonsense(self, query: str) -> bool:
        trimmed = query.strip()
        if not trimmed:
            return True
        # If there are no letters or digits, it's nonsense (e.g., "!!!???").
        return not any(ch.isalnum() for ch in trimmed)

    def _log_classification(self, query: str, classification: Classification) -> Dict[str, Any]:
        tools = classification.to_dict()
        if self.logger:
            payload = dict(tools)
            payload["query"] = query
            self.logger.log("classify_query", **payload)
        return tools
