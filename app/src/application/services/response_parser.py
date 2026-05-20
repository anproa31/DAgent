"""Parse LLM analysis responses into structured content blocks."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Protocol


class VariableResolver(Protocol):
    async def get_variable_value(
        self, analysis_id: str, variable_name: str
    ) -> Dict[str, Any] | None: ...


def del_think_tag(content: str) -> str:
    return re.sub(
        r"<think>.*?</think>", "", content, flags=re.DOTALL
    )


async def parse_response_to_content(
    response: str,
    analysis_id: str,
    resolver: VariableResolver,
    *,
    ignore_errors: bool = True,
) -> List[Dict[str, Any]]:
    """Parse the AI response and convert to content format."""
    content: List[Dict[str, Any]] = []

    if not isinstance(response, str):
        raise TypeError(f"response must be str, got {type(response).__name__}")

    match = re.search(r"<report>(.*?)</report>", response, re.IGNORECASE | re.DOTALL)
    report_content = match.group(1) if match else response

    variable_pattern = r"\{([^\{\}]+?)\}"
    variables_iter = list(re.finditer(variable_pattern, report_content))
    cursor = 0

    for var_match in variables_iter:
        var_name = var_match.group(1)

        before_text = report_content[cursor : var_match.start()]
        if before_text.strip():
            content.append({"type": "markdown", "content": before_text.strip()})

        try:
            var_result = await resolver.get_variable_value(analysis_id, var_name)
        except Exception as e:
            if ignore_errors:
                cursor = var_match.end()
                continue
            raise

        if var_result and isinstance(var_result, dict):
            if "result" in var_result and isinstance(var_result["result"], list):
                for var_content in var_result["result"]:
                    var_type = var_content.get("type", "string")
                    data = var_content.get("data")
                    if var_type == "string" and data in (None, "None"):
                        continue
                    if var_type == "image":
                        content.append({"type": "image", "base64": data})
                    elif var_type == "table":
                        content.append({"type": "table", "table": data})
                    else:
                        content.append({"type": "variable", "data": data})
            elif "error" in var_result and not ignore_errors:
                raise ValueError(
                    f"Variable retrieval error for {var_name}: {var_result['error']}"
                )
        elif not ignore_errors:
            raise ValueError(f"No data returned for variable '{var_name}'")

        cursor = var_match.end()

    remaining_text = report_content[cursor:]
    if remaining_text.strip():
        content.append({"type": "markdown", "content": remaining_text.strip()})

    return content
