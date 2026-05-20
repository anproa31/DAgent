"""Legacy router re-exports — prefer ``api.routes`` for new code."""
from ..api.routes.analysis import router as new_analysis_router
from ..api.routes.datasources import router as data_router
from ..api.routes.health import router as health_router
from ..api.routes.internal import router as internal_router
from ..api.routes.models import router as model_list_router

__all__ = [
    "data_router",
    "health_router",
    "new_analysis_router",
    "model_list_router",
    "internal_router",
]
