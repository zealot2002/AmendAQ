from __future__ import annotations

import json
import re
from typing import Any, Protocol

from mycs.db.schema_kg import KG_SCHEMA_FOR_LLM
from mycs.log import get_logger

logger = get_logger(__name__)

_FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|ATTACH|DETACH|PRAGMA|REPLACE)\b",
    re.I,
)


class SqlGenerator(Protocol):
    def nl_to_sql(self, question: str, *, document_id: str | None = None) -> str: ...


class OllamaSqlGenerator:
    def __init__(self, llm: Any) -> None:
        self._llm = llm

    def nl_to_sql(self, question: str, *, document_id: str | None = None) -> str:
        system = (
            "你是 SQLite 只读查询生成器。根据用户问题生成单条 SELECT。"
            f"Schema:\n{KG_SCHEMA_FOR_LLM}\n"
            f"若已知 document_id={document_id!r}，请在 WHERE 中过滤 e.document_id。"
            "只输出 JSON：{\"sql\":\"SELECT ...\"} LIMIT 必须 <= 20。"
        )
        user = json.dumps({"question": question, "document_id": document_id}, ensure_ascii=False)
        data = self._llm._json_chat(system, user)  # type: ignore[attr-defined]
        sql = str(data.get("sql") or "").strip()
        validate_readonly_sql(sql)
        return sql


def validate_readonly_sql(sql: str) -> None:
    s = sql.strip().rstrip(";")
    if not s.upper().startswith("SELECT"):
        raise ValueError("only SELECT allowed")
    if _FORBIDDEN.search(s):
        raise ValueError("forbidden SQL keyword")
    if ";" in s:
        raise ValueError("multi-statement not allowed")
    if not re.search(r"\bkg_", s, re.I):
        raise ValueError("query must reference kg_ tables")


def create_sql_generator() -> SqlGenerator:
    from mycs.llm.factory import create_llm

    return OllamaSqlGenerator(create_llm())
