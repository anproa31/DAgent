"""Security helpers (adapted from dbgpt-sandbox)."""
from __future__ import annotations

from typing import List


class SecurityUtils:
    @staticmethod
    def validate_code(code: str, language: str) -> List[str]:
        warnings: List[str] = []

        if language in ("bash", "shell"):
            bash_patterns = [
                ("rm -rf /", "recursive root deletion"),
                ("mkfs.", "disk format"),
                ("dd if=", "direct disk write"),
                (":(){ :|:& };:", "fork bomb"),
            ]
            code_lower = code.lower()
            for pattern, desc in bash_patterns:
                if pattern in code_lower:
                    warnings.append(f"Potential dangerous operation: {desc} ({pattern})")
            return warnings

        dangerous_patterns = [
            "subprocess",
            "__import__",
            "eval(",
            "exec(",
            "socket",
            "urllib",
            "requests",
        ]
        code_lower = code.lower()
        for pattern in dangerous_patterns:
            if pattern in code_lower:
                warnings.append(f"Potential dangerous operation: {pattern}")

        if language == "python" and "pickle" in code_lower:
            warnings.append("pickle module usage may be unsafe")

        return warnings
