"""Structured tool output chunks (aligned with DB-GPT agentic_data_api format)."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional


def text_chunk(content: str) -> Dict[str, str]:
    return {"output_type": "text", "content": content}


def code_chunk(content: str) -> Dict[str, str]:
    return {"output_type": "code", "content": content}


def table_chunk(data: Any) -> Dict[str, Any]:
    return {"output_type": "table", "content": data}


def image_chunk(base64_data: str) -> Dict[str, str]:
    return {"output_type": "image", "content": base64_data}


def variable_chunk(data: Any, var_type: str = "string") -> Dict[str, Any]:
    return {"output_type": "variable", "var_type": var_type, "content": data}


def chunks_to_json(chunks: List[Dict[str, Any]]) -> str:
    return json.dumps({"chunks": chunks}, ensure_ascii=False)


def content_blocks_from_variable_result(
    var_result: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Convert sandbox /var response items into UI content blocks."""
    if not var_result or "result" not in var_result:
        return []

    blocks: List[Dict[str, Any]] = []
    for item in var_result["result"]:
        var_type = item.get("type", "string")
        data = item.get("data")
        if var_type == "image":
            blocks.append({"type": "image", "base64": data})
        elif var_type == "table":
            blocks.append({"type": "table", "table": data})
        else:
            blocks.append({"type": "variable", "data": data})
    return blocks
