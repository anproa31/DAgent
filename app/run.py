"""
Run the API locally without guessing the uvicorn target.

Wrong (breaks relative imports in ``main.py``):

  cd src && uvicorn main:app --reload

Right:

  cd app && python run.py

  # or:  uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import uvicorn

from src.core.config import get_settings

if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(
        "src.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
    )
