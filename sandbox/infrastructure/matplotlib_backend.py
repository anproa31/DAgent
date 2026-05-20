"""Configure headless matplotlib before pyplot is imported elsewhere."""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
