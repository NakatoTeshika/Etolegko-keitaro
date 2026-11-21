import os
import re
from functools import partial

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.config import KEITARO_API_KEY, KEITARO_BASE_URL
from app.keitaro_client import fetch_offers, post_to_keitaro, find_campaign_by_name
from app.services.campaign_creator import (
    CampaignCreationError,
    create_campaign_with_streams,
)

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


class CampaignCreate(BaseModel):
    name: str
    geo: str
    offer_id: int = Field(gt=0)


def read_required_id(variable: str) -> int:
    value = os.getenv(variable, "").strip()
    try:
        identifier = int(value)
        if identifier > 0:
            return identifier
    except ValueError:
        pass

    raise HTTPException(500, f"Укажи положительный ID в {variable} в .env")


@router.post("", status_code=201)
def create_campaign(request: CampaignCreate) -> dict:
    name = request.name.strip()
    geo = request.geo.strip().upper()

    if not name:
        raise HTTPException(422, "Введи название кампании")
    if not re.fullmatch(r"[A-Z]{2}", geo):
        raise HTTPException(422, "Введи двухбуквенный код страны, например MX")

    if not KEITARO_BASE_URL or not KEITARO_API_KEY:
        raise HTTPException(500, "Укажи адрес и API-ключ Keitaro в .env")

    try:
        existing = find_campaign_by_name(
            KEITARO_BASE_URL, KEITARO_API_KEY, name
        )
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as error:
        raise HTTPException(
            status_code=502,
            detail="Не удалось проверить список кампаний в Keitaro.",
        ) from error

    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Кампания «{existing['name']}» уже существует. ID: {existing['id']}.",
        )

    domain_id = read_required_id("KEITARO_DOMAIN_ID")
    group_id = read_required_id("KEITARO_CAMPAIGN_GROUP_ID")
    traffic_source_id = read_required_id("KEITARO_TRAFFIC_SOURCE_ID")

    try:
        offers = fetch_offers(KEITARO_BASE_URL, KEITARO_API_KEY)
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as error:
        raise HTTPException(502, "Не удалось прочитать каталог Keitaro") from error

    if not any(offer["id"] == request.offer_id for offer in offers):
        raise HTTPException(404, "Оффер не найден в каталоге Keitaro")

    post = partial(post_to_keitaro, KEITARO_BASE_URL, KEITARO_API_KEY)
    try:
        return create_campaign_with_streams(
            post,
            name=name,
            geo=geo,
            offer_id=request.offer_id,
            domain_id=domain_id,
            group_id=group_id,
            traffic_source_id=traffic_source_id,
        )
    except CampaignCreationError as error:
        raise HTTPException(502, str(error)) from error