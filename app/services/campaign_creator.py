from typing import Callable
from uuid import uuid4

import httpx


class CampaignCreationError(RuntimeError):
    pass


def create_campaign_with_streams(
    post: Callable[[str, dict], dict],
    *,
    name: str,
    geo: str,
    offer_id: int,
    domain_id: int,
    group_id: int,
    traffic_source_id: int,
) -> dict:
    alias = f"test-{uuid4().hex[:12]}"
    campaign_id = None
    stage = "создание кампании"

    try:
        campaign = post(
            "campaigns",
            {
                "name": name,
                "alias": alias,
                "type": "position",
                "state": "disabled",
                "domain_id": domain_id,
                "group_id": str(group_id),
                "traffic_source_id": traffic_source_id,
            },
        )
        campaign_id = campaign["id"]

        stage = "создание потока с фильтром страны"
        redirect_stream = post(
            "streams",
            {
                "campaign_id": campaign_id,
                "name": f"{geo} → Google",
                "position": 1,
                "type": "regular",
                "schema": "redirect",
                "action_type": "http",
                "action_payload": "https://google.com",
                "filters": [
                    {"name": "country", "mode": "accept", "payload": [geo]}
                ],
            },
        )

        stage = "создание потока с оффером"
        offer_stream = post(
            "streams",
            {
                "campaign_id": campaign_id,
                "name": "Офферы",
                "position": 2,
                "type": "default",
                "schema": "landings",
                "action_type": "http",
                "offers": [
                    {"offer_id": offer_id, "share": 100, "state": "active"}
                ],
            },
        )

        stage = "включение кампании"
        post(f"campaigns/{campaign_id}/enable", None)

    except (httpx.HTTPError, ValueError, KeyError, TypeError) as error:
        reference = f"alias={alias}"
        if campaign_id is not None:
            reference += f", campaign_id={campaign_id}"
        reason = (
            f"HTTP {error.response.status_code}"
            if isinstance(error, httpx.HTTPStatusError)
            else "сбой запроса или неожиданный ответ"
        )
        raise CampaignCreationError(
            f"Этап «{stage}» — {reason}. Проверь кампанию в Keitaro ({reference})."
        ) from error

    return {
        "id": campaign_id,
        "name": name,
        "alias": alias,
        "redirect_stream_id": redirect_stream.get("id"),
        "offer_stream_id": offer_stream.get("id"),
    }