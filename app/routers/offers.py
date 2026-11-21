import httpx
from fastapi import APIRouter, HTTPException

from app.config import KEITARO_API_KEY, KEITARO_BASE_URL
from app.keitaro_client import fetch_offers

router = APIRouter()


@router.get("/offers")
def get_offers() -> list[dict]:
    if not KEITARO_BASE_URL or not KEITARO_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="Укажи KEITARO_BASE_URL и KEITARO_API_KEY в .env",
        )

    try:
        return fetch_offers(KEITARO_BASE_URL, KEITARO_API_KEY)
    except httpx.HTTPStatusError as error:
        raise HTTPException(
            status_code=502,
            detail=f"Keitaro вернул HTTP {error.response.status_code}",
        ) from error
    except httpx.RequestError as error:
        raise HTTPException(
            status_code=502,
            detail="Не удалось подключиться к Keitaro",
        ) from error