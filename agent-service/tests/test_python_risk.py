"""Tests for Python risk tiering (solution.md §5)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agents.executor.python_risk import HIGH, MEDIUM, SAFE, assess_python_risk  # noqa: E402


def test_safe_pandas_code():
    code = "df = duckdb_conn.execute('SELECT * FROM v').fetchdf()\nresult = df.groupby('a').mean()"
    assert assess_python_risk(code) == SAFE


def test_medium_file_write():
    assert assess_python_risk("df.to_csv('out.csv')") == MEDIUM
    assert assess_python_risk("with open('f.txt', 'w') as fh: fh.write('x')") == MEDIUM


def test_high_network_or_os():
    assert assess_python_risk("import os\nos.system('ls')") == HIGH
    assert assess_python_risk("import requests\nrequests.get('http://x')") == HIGH
    assert assess_python_risk("import subprocess") == HIGH


def test_high_takes_precedence_over_medium():
    code = "import os\ndf.to_csv('out.csv')"
    assert assess_python_risk(code) == HIGH
