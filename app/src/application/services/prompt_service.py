"""Prompt template loading and schema cache management."""
from __future__ import annotations

import os
from typing import Dict, Iterable, List, Optional

from ...datasource_registry import get_registry


class PromptService:
    def __init__(self) -> None:
        prompts_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "prompts"
        )
        with open(os.path.join(prompts_dir, "prompt-v3.txt"), "r", encoding="utf-8") as f:
            self.prompt_text = f.read()
        with open(
            os.path.join(prompts_dir, "prompt-v3+.txt"), "r", encoding="utf-8"
        ) as f:
            self.prompt_text_with_example = f.read()
        self._schema_by_view: Dict[str, str] = {}

    def refresh_schema_cache(self) -> None:
        schema_by_view: Dict[str, str] = {}
        for record in get_registry().list_datasources():
            if not record.schema_markdown:
                continue
            for view_name in record.view_names:
                schema_by_view[view_name] = record.schema_markdown
        self._schema_by_view = schema_by_view

    def is_database_registered(self) -> bool:
        if self._schema_by_view:
            return True
        return any(get_registry().list_datasources())

    def get_db_embedded_prompt(self, tables: Iterable[str] | None = None) -> List[str]:
        tables = list(tables or [])
        if not tables:
            tables = list(self._schema_by_view.keys())

        seen: set[str] = set()
        info_parts: List[str] = []
        for table in tables:
            block = self._schema_by_view.get(table)
            if not block or block in seen:
                continue
            seen.add(block)
            info_parts.append(block)

        dbinfo = "\n\n".join(info_parts)
        return [
            self.prompt_text_with_example.replace("@databaseinfo", dbinfo),
            self.prompt_text.replace("@databaseinfo", dbinfo),
        ]


_service: Optional[PromptService] = None


def get_prompt_service() -> PromptService:
    global _service
    if _service is None:
        _service = PromptService()
    return _service


def reset_prompt_service() -> None:
    global _service
    _service = None
