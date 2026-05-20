import pytest

from src.application.services.response_parser import del_think_tag, parse_response_to_content


class FakeResolver:
    async def get_variable_value(self, analysis_id: str, variable_name: str):
        if variable_name == "chart":
            return {
                "result": [{"type": "table", "data": [{"a": 1}]}],
            }
        return None


@pytest.mark.asyncio
async def test_parse_response_to_content_with_variable():
    response = "<report>Summary {chart} end</report>"
    content = await parse_response_to_content(response, "id-1", FakeResolver())
    types = [block["type"] for block in content]
    assert "markdown" in types
    assert "table" in types


def test_del_think_tag():
    text = "before<think>secret</think>after"
    result = del_think_tag(text)
    assert "secret" not in result
    assert "before" in result
    assert "after" in result
