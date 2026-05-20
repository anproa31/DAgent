from .analysis import router as analysis_router
from .datasources import router as datasources_router
from .health import router as health_router
from .internal import router as internal_router
from .models import router as models_router
from .v1 import v1_router

__all__ = [
    "analysis_router",
    "datasources_router",
    "health_router",
    "internal_router",
    "models_router",
    "v1_router",
]
