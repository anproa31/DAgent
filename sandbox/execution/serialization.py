"""Serialize session variables for API responses (tables, images, strings)."""
from __future__ import annotations

import base64
import io
from typing import Any, Dict, List

import pandas as pd


def _is_matplotlib_figure(value: Any) -> bool:
    return type(value).__module__ == "matplotlib.figure" and type(value).__name__ == "Figure"


def to_json(value: Any) -> Dict[str, Any]:
    if isinstance(value, pd.DataFrame):
        df_copy = value.copy()
        if not df_copy.index.equals(pd.RangeIndex(len(df_copy))):
            df_copy.insert(0, "", df_copy.index)
        return {"data": df_copy.to_json(orient="records"), "type": "table"}
    if isinstance(value, pd.Series):
        series_copy = value.copy()
        df_from_series = pd.DataFrame([series_copy])
        if not series_copy.index.equals(pd.RangeIndex(len(series_copy))):
            df_from_series.insert(0, "", series_copy.index)
        return {"data": df_from_series.to_json(orient="records"), "type": "table"}
    if _is_matplotlib_figure(value):
        import matplotlib.pyplot as plt

        buf = io.BytesIO()
        value.savefig(buf, format="png", dpi=150, bbox_inches="tight")
        buf.seek(0)
        encoded = base64.b64encode(buf.getvalue()).decode("utf-8")
        plt.close(value)
        return {"data": encoded, "type": "image"}
    return {"data": str(value), "type": "string"}


def to_response_payload(value: Any) -> List[Dict[str, Any]]:
    if isinstance(value, list):
        return [to_json(item) for item in value]
    if isinstance(value, dict):
        out: List[Dict[str, Any]] = []
        for key, val in value.items():
            out.append({"data": str(key), "type": "string"})
            out.append(to_json(val))
        return out
    return [to_json(value)]
