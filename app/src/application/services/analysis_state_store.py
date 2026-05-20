"""In-memory store for analysis and space session state."""
from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional


class AnalysisStateStore:
    """Thread-safe in-memory analysis, space, and history state."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.analysis_states: Dict[str, Dict[str, Any]] = {}
        self.spaces: Dict[str, List[str]] = {}
        self.space_history: Dict[str, List[List[Dict]]] = {}

    def create_space(self, space_id: str) -> None:
        with self._lock:
            self.spaces[space_id] = []
            self.space_history[space_id] = []

    def get_space(self, space_id: str) -> List[str]:
        with self._lock:
            return list(self.spaces.get(space_id, []))

    def delete_space(self, space_id: str) -> bool:
        with self._lock:
            if space_id not in self.spaces:
                return False
            for analysis_id in self.spaces[space_id]:
                self.analysis_states.pop(analysis_id, None)
            del self.spaces[space_id]
            self.space_history.pop(space_id, None)
            return True

    def ensure_space(self, space_id: str) -> None:
        with self._lock:
            if space_id not in self.spaces:
                self.spaces[space_id] = []
                self.space_history[space_id] = []

    def append_analysis(self, space_id: str, analysis_id: str) -> None:
        with self._lock:
            self.spaces[space_id].append(analysis_id)

    def truncate_space_history(self, space_id: str, index: int) -> None:
        with self._lock:
            del self.space_history[space_id][index:]
            del self.spaces[space_id][index:]

    def set_analysis(self, analysis_id: str, state: Dict[str, Any]) -> None:
        with self._lock:
            self.analysis_states[analysis_id] = state

    def get_analysis(self, analysis_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            state = self.analysis_states.get(analysis_id)
            return state.copy() if state else None

    def get_analysis_ref(self, analysis_id: str) -> Optional[Dict[str, Any]]:
        """Return live mutable state dict (for async task updates)."""
        with self._lock:
            return self.analysis_states.get(analysis_id)

    def append_history(self, space_id: str, entry: List[Dict]) -> None:
        with self._lock:
            self.space_history[space_id].append(entry)

    def get_history(self, space_id: str) -> List[List[Dict]]:
        with self._lock:
            return list(self.space_history.get(space_id, []))

    def space_analysis_count(self, space_id: str) -> int:
        with self._lock:
            return len(self.spaces.get(space_id, []))

    def clear(self) -> None:
        with self._lock:
            self.analysis_states.clear()
            self.spaces.clear()
            self.space_history.clear()


_store: Optional[AnalysisStateStore] = None


def get_analysis_state_store() -> AnalysisStateStore:
    global _store
    if _store is None:
        _store = AnalysisStateStore()
    return _store


def reset_analysis_state_store() -> None:
    global _store
    _store = None
