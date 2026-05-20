"""Domain-level exceptions (no HTTP/framework coupling)."""


class DomainError(Exception):
    """Base class for domain errors."""


class ValidationError(DomainError):
    """Input or business-rule validation failed."""


class DatasourceNotFoundError(DomainError):
    """Requested datasource does not exist."""


class AnalysisNotFoundError(DomainError):
    """Requested analysis does not exist."""


class UnsupportedFileTypeError(ValidationError):
    """Uploaded file type is not supported."""
