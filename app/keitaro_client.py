import httpx
from typing import Optional


def fetch_offers(base_url: str, api_key: str) -> list[dict]:
    response = httpx.get(
        f"{base_url}/admin_api/v1/offers",
        headers={"Api-Key": api_key},
        timeout=10.0,
    )
    response.raise_for_status()

    return [
        {"id": offer["id"], "name": offer["name"]}
        for offer in response.json()
    ]

def fetch_campaign_streams(
    base_url: str,
    api_key: str,
    campaign_id: int,
) -> list[dict]:
    response = httpx.get(
        f"{base_url}/admin_api/v1/campaigns/{campaign_id}/streams",
        headers={"Api-Key": api_key},
        timeout=10.0,
    )
    response.raise_for_status()
    return response.json()

def fetch_stream(base_url: str, api_key: str, stream_id: int) -> dict:
    response = httpx.get(
        f"{base_url}/admin_api/v1/streams/{stream_id}",
        headers={"Api-Key": api_key},
        timeout=10.0,
    )
    response.raise_for_status()
    return response.json()


def update_stream_offers(
    base_url: str,
    api_key: str,
    stream_id: int,
    offers: list[dict],
) -> dict:
    response = httpx.put(
        f"{base_url}/admin_api/v1/streams/{stream_id}",
        headers={"Api-Key": api_key},
        json={"offers": offers},
        timeout=10.0,
    )
    response.raise_for_status()
    return response.json()

def post_to_keitaro(
    base_url: str,
    api_key: str,
    path: str,
    payload: Optional[dict] = None,
) -> dict:
    options = {"json": payload} if payload is not None else {}

    response = httpx.post(
        f"{base_url}/admin_api/v1/{path}",
        headers={"Api-Key": api_key},
        timeout=10.0,
        **options,
    )
    response.raise_for_status()
    return response.json()

def find_campaign_by_name(
    base_url: str,
    api_key: str,
    name: str,
) -> Optional[dict]:
    target = name.strip().casefold()
    limit = 100
    offset = 0

    with httpx.Client(headers={"Api-Key": api_key}, timeout=10.0) as client:
        while True:
            response = client.get(
                f"{base_url}/admin_api/v1/campaigns",
                params={"limit": limit, "offset": offset},
            )
            response.raise_for_status()
            campaigns = response.json()

            for campaign in campaigns:
                if campaign["name"].strip().casefold() == target:
                    return campaign

            if len(campaigns) < limit:
                return None

            offset += len(campaigns)