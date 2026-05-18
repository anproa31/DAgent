"""
Run the API locally without guessing the uvicorn target.

Wrong (breaks relative imports in ``main.py``):

  cd src && uvicorn main:app --reload

Right:

  cd app && python run.py

  # or:  uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import os

import uvicorn

if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(
        "src.main:app",
        host=host,
        port=port,
        reload=os.environ.get("RELOAD", "1") not in ("0", "false", "False"),
    )
