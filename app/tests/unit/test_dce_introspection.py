import pytest

from src.dce_introspection import normalize_identifier, parse_connection_string


def test_normalize_identifier_basic():
    assert normalize_identifier("My Table Name") == "my_table_name"


def test_normalize_identifier_rejects_empty():
    with pytest.raises(ValueError):
        normalize_identifier("")


def test_parse_connection_string_postgres():
    parsed = parse_connection_string("postgresql://user:pass@localhost:5432/mydb")
    assert parsed["host"] == "localhost"
    assert parsed["port"] == 5432
    assert parsed["database"] == "mydb"
    assert parsed["user"] == "user"
    assert parsed["password"] == "pass"
