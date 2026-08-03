from fastapi import APIRouter

from app.settings import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "data_mode": settings.data_mode.value,
    }
