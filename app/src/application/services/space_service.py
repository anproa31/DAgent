"""Space lifecycle management."""
from __future__ import annotations

import uuid

from .analysis_state_store import AnalysisStateStore, get_analysis_state_store


class SpaceService:
    def __init__(self, store: AnalysisStateStore | None = None) -> None:
        self._store = store or get_analysis_state_store()

    def create_space(self) -> str:
        space_id = str(uuid.uuid4())
        self._store.create_space(space_id)
        return space_id

    def get_space(self, space_id: str) -> list[str]:
        return self._store.get_space(space_id)

    def delete_space(self, space_id: str) -> bool:
        return self._store.delete_space(space_id)
