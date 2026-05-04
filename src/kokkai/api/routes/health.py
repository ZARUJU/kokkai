from fastapi import APIRouter

from kokkai.api.schemas import HealthOut


router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthOut)
def health() -> HealthOut:
    return {"status": "ok"}
