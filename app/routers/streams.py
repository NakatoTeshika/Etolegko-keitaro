import httpx
from fastapi import APIRouter, HTTPException

from app.config import KEITARO_API_KEY, KEITARO_BASE_URL
from app.database import SessionLocal
from app.keitaro_client import fetch_campaign_streams, fetch_offers
from app.services.stream_editor import (
    DraftConflict,
    MissingOfferName,
    read_campaign_streams,
    sync_campaign_streams, cancel_stream_draft, set_draft_offer_pinned,
)

from sqlalchemy import text

from app.services.shares import InvalidDistribution
from app.services.stream_editor import (
    OfferEditConflict,
    StreamNotFound,
    add_offer_to_draft,
)

from pydantic import BaseModel

from app.services.stream_editor import OfferLinkNotFound, set_draft_offer_active

from functools import partial

from app.keitaro_client import fetch_stream, update_stream_offers
from app.services.stream_editor import PublishedOffersMismatch, publish_stream_draft
router = APIRouter(prefix="/campaigns", tags=["campaign streams"])


@router.post("/{campaign_id}/fetch")
def fetch_streams(campaign_id: int) -> list[dict]:
    if not KEITARO_BASE_URL or not KEITARO_API_KEY:
        raise HTTPException(500, "Укажи адрес и API-ключ Keitaro в .env")

    try:
        streams = fetch_campaign_streams(
            KEITARO_BASE_URL, KEITARO_API_KEY, campaign_id
        )
        offers = fetch_offers(KEITARO_BASE_URL, KEITARO_API_KEY)
    except httpx.HTTPStatusError as error:
        raise HTTPException(
            502, f"Keitaro вернул HTTP {error.response.status_code}"
        ) from error
    except httpx.RequestError as error:
        raise HTTPException(502, "Не удалось подключиться к Keitaro") from error

    offer_names = {offer["id"]: offer["name"] for offer in offers}

    try:
        with SessionLocal.begin() as session:
            sync_campaign_streams(session, campaign_id, streams, offer_names)
            return read_campaign_streams(session, campaign_id)
    except DraftConflict as error:
        raise HTTPException(
            409, "Сначала опубликуй или отмени черновики этой кампании"
        ) from error
    except MissingOfferName as error:
        raise HTTPException(
            502, f"Keitaro не вернул название оффера {error.args[0]}"
        ) from error


@router.get("/{campaign_id}/streams")
def get_streams(campaign_id: int) -> list[dict]:
    with SessionLocal() as session:
        return read_campaign_streams(session, campaign_id)

@router.post("/{campaign_id}/streams/{stream_id}/offers/{offer_id}")
def add_offer(campaign_id: int, stream_id: int, offer_id: int) -> list[dict]:
    if not KEITARO_BASE_URL or not KEITARO_API_KEY:
        raise HTTPException(500, "Укажи адрес и API-ключ Keitaro в .env")

    try:
        catalog = fetch_offers(KEITARO_BASE_URL, KEITARO_API_KEY)
    except httpx.HTTPStatusError as error:
        raise HTTPException(
            502, f"Keitaro вернул HTTP {error.response.status_code}"
        ) from error
    except httpx.RequestError as error:
        raise HTTPException(502, "Не удалось подключиться к Keitaro") from error

    offer = next((item for item in catalog if item["id"] == offer_id), None)
    if offer is None:
        raise HTTPException(404, "Оффер не найден в каталоге Keitaro")

    try:
        with SessionLocal.begin() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            add_offer_to_draft(session, campaign_id, stream_id, offer_id, offer["name"])
            return read_campaign_streams(session, campaign_id)
    except StreamNotFound as error:
        raise HTTPException(404, "Поток не найден в этой кампании") from error
    except (OfferEditConflict, InvalidDistribution) as error:
        raise HTTPException(409, str(error)) from error

@router.post("/{campaign_id}/streams/{stream_id}/cancel")
def cancel_draft(campaign_id: int, stream_id: int) -> list[dict]:
    try:
        with SessionLocal.begin() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            cancel_stream_draft(session, campaign_id, stream_id)
            return read_campaign_streams(session, campaign_id)
    except StreamNotFound as error:
        raise HTTPException(
            status_code=404,
            detail="Поток не найден в этой кампании",
        ) from error

class OfferActivityUpdate(BaseModel):
    active: bool


@router.patch("/{campaign_id}/streams/{stream_id}/offers/{offer_id}")
def update_offer_activity(
    campaign_id: int,
    stream_id: int,
    offer_id: int,
    update: OfferActivityUpdate,
) -> list[dict]:
    try:
        with SessionLocal.begin() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            set_draft_offer_active(
                session, campaign_id, stream_id, offer_id, update.active
            )
            return read_campaign_streams(session, campaign_id)
    except StreamNotFound as error:
        raise HTTPException(404, "Поток не найден в этой кампании") from error
    except OfferLinkNotFound as error:
        raise HTTPException(404, "Оффер не найден в этом потоке") from error
    except InvalidDistribution as error:
        raise HTTPException(409, str(error)) from error

class OfferPinUpdate(BaseModel):
    pinned: bool


@router.patch("/{campaign_id}/streams/{stream_id}/offers/{offer_id}/pin")
def update_offer_pin(
    campaign_id: int,
    stream_id: int,
    offer_id: int,
    update: OfferPinUpdate,
) -> list[dict]:
    try:
        with SessionLocal.begin() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            set_draft_offer_pinned(
                session, campaign_id, stream_id, offer_id, update.pinned
            )
            return read_campaign_streams(session, campaign_id)
    except StreamNotFound as error:
        raise HTTPException(404, "Поток не найден в этой кампании") from error
    except OfferLinkNotFound as error:
        raise HTTPException(404, "Оффер не найден в этом потоке") from error
    except OfferEditConflict as error:
        raise HTTPException(409, str(error)) from error

@router.post("/{campaign_id}/streams/{stream_id}/push")
def push_draft(campaign_id: int, stream_id: int) -> list[dict]:
    if not KEITARO_BASE_URL or not KEITARO_API_KEY:
        raise HTTPException(500, "Укажи адрес и API-ключ Keitaro в .env")

    try:
        with SessionLocal.begin() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            publish_stream_draft(
                session,
                campaign_id,
                stream_id,
                get_remote_stream=partial(
                    fetch_stream, KEITARO_BASE_URL, KEITARO_API_KEY
                ),
                update_remote_offers=partial(
                    update_stream_offers, KEITARO_BASE_URL, KEITARO_API_KEY
                ),
            )
            return read_campaign_streams(session, campaign_id)
    except StreamNotFound as error:
        raise HTTPException(404, "Поток не найден в этой кампании") from error
    except OfferEditConflict as error:
        raise HTTPException(409, str(error)) from error
    except PublishedOffersMismatch as error:
        raise HTTPException(502, "Keitaro вернул доли, отличные от черновика") from error
    except httpx.HTTPStatusError as error:
        raise HTTPException(
            502, f"Keitaro вернул HTTP {error.response.status_code}"
        ) from error
    except httpx.RequestError as error:
        raise HTTPException(502, "Не удалось подключиться к Keitaro") from error