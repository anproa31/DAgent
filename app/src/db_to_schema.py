"""Schema retrieval shim.

The historical ``main(engine)`` function read schema from a PostgreSQL
SQLAlchemy engine. The multi-datasource refactor replaces that with the
:class:`DatasourceRegistry`, which already pre-computes Markdown per
datasource. This module is now a thin facade kept for backwards
compatibility with callers that ``from ..db_to_schema import main``.
"""
from __future__ import annotations

from typing import Any, Dict

from .datasource_registry import get_registry


def main(_engine: Any = None) -> Dict[str, str]:
    """Return ``{view_name: markdown_block}`` for every registered datasource.

    The ``_engine`` argument is accepted for backwards compatibility but
    ignored: schema now comes from the datasource registry instead of a
    PostgreSQL engine.
    """
    registry = get_registry()
    schema_by_view: Dict[str, str] = {}
    for record in registry.list_datasources():
        if not record.schema_markdown:
            continue
        # Map each view name in this datasource to the same combined markdown
        # block so callers that filter by ``tables=[...]`` still get useful
        # context for the datasource the table belongs to.
        for view_name in record.view_names:
            schema_by_view[view_name] = record.schema_markdown
    if not schema_by_view:
        return {}
    return schema_by_view
