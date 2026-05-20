"""Sandbox runtime base abstractions (from dbgpt-sandbox)."""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ExecutionStatus(Enum):
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    RESOURCE_LIMIT = "resource_limit"


@dataclass
class ExecutionResult:
    status: ExecutionStatus
    output: str = ""
    error: str = ""
    execution_time: float = 0.0
    memory_usage: int = 0
    exit_code: int = 0
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "status": self.status.value,
            "output": self.output,
            "error": self.error,
            "execution_time": self.execution_time,
            "memory_usage": self.memory_usage,
            "exit_code": self.exit_code,
        }
        if self.payload:
            result.update(self.payload)
        return result


@dataclass
class SessionConfig:
    language: str = "python"
    timeout: int = 30
    max_memory: int = 256 * 1024 * 1024
    max_cpus: int = 1
    working_dir: str = "/workspace"
    environment_vars: Dict[str, str] = field(default_factory=dict)
    network_disabled: bool = False


class SandboxSession(ABC):
    def __init__(self, session_id: str, config: SessionConfig):
        self.session_id = session_id
        self.config = config
        self.created_at = time.time()
        self.last_accessed = time.time()
        self._is_active = False

    @property
    def is_active(self) -> bool:
        return self._is_active

    @abstractmethod
    def start(self) -> bool:
        pass

    @abstractmethod
    def stop(self) -> bool:
        pass

    @abstractmethod
    def execute(self, code: str) -> ExecutionResult:
        pass

    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        pass

    def update_last_accessed(self) -> None:
        self.last_accessed = time.time()


class SandboxRuntime(ABC):
    def __init__(self, runtime_id: str):
        self.runtime_id = runtime_id
        self.sessions: Dict[str, SandboxSession] = {}

    @abstractmethod
    def create_session(self, session_id: str, config: SessionConfig) -> SandboxSession:
        pass

    @abstractmethod
    def destroy_session(self, session_id: str) -> bool:
        pass

    @abstractmethod
    def list_sessions(self) -> List[str]:
        pass

    @abstractmethod
    def get_session(self, session_id: str) -> Optional[SandboxSession]:
        pass

    @abstractmethod
    def cleanup_expired_sessions(self, max_idle_time: int = 3600) -> int:
        pass

    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        pass

    @abstractmethod
    def supports_language(self, language: str) -> bool:
        pass
