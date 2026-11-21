from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Offer, Stream, StreamOffer
from app.services.shares import distribute_shares
from typing import Callable

class DraftConflict(Exception):
    pass


class MissingOfferName(Exception):
    pass


def sync_campaign_streams(
    session: Session,
    campaign_id: int,
    remote_streams: list[dict],
    offer_names: dict[int, str],
) -> None:
    local_streams = session.scalars(
        select(Stream).where(Stream.campaign_id == campaign_id)
    )
    streams_by_id = {stream.id: stream for stream in local_streams}

    if any(stream.has_draft for stream in streams_by_id.values()):
        raise DraftConflict

    for remote_stream in remote_streams:
        stream_id = remote_stream["id"]
        stream = streams_by_id.get(stream_id)

        if stream is None:
            stream = Stream(id=stream_id, campaign_id=campaign_id)
            session.add(stream)

        stream.name = remote_stream["name"]


    # Сохраняем родительские строки до привязок к ним.
    session.flush()

    for remote_stream in remote_streams:
        _sync_stream_offers(session, remote_stream, offer_names)


def _sync_stream_offers(
    session: Session,
    remote_stream: dict,
    offer_names: dict[int, str],
) -> None:
    stream_id = remote_stream["id"]
    links = session.scalars(
        select(StreamOffer).where(StreamOffer.stream_id == stream_id)
    )
    links_by_offer = {link.offer_id: link for link in links}

    active_offers = {
        item["offer_id"]: item["share"]
        for item in (remote_stream.get("offers") or [])
        if item.get("state", "active") == "active"
    }

    for offer_id, link in links_by_offer.items():
        if offer_id not in active_offers:
            link.published_share = None
            link.published_pinned = False

    for offer_id, share in active_offers.items():
        offer = session.get(Offer, offer_id)
        name = offer_names.get(offer_id)

        if offer is None:
            if name is None:
                raise MissingOfferName(offer_id)
            session.add(Offer(id=offer_id, name=name))
            session.flush()
        elif name is not None:
            offer.name = name

        link = links_by_offer.get(offer_id)
        if link is None:
            link = StreamOffer(stream_id=stream_id, offer_id=offer_id)
            session.add(link)

        link.published_share = share
        link.was_published = True


def read_campaign_streams(session: Session, campaign_id: int) -> list[dict]:
    rows = session.execute(
        select(Stream, StreamOffer, Offer)
        .outerjoin(StreamOffer, StreamOffer.stream_id == Stream.id)
        .outerjoin(Offer, Offer.id == StreamOffer.offer_id)
        .where(Stream.campaign_id == campaign_id)
        .order_by(Stream.id, StreamOffer.offer_id)
    )

    streams = {}
    for stream, link, offer in rows:
        result = streams.setdefault(
            stream.id,
            {
                "id": stream.id,
                "name": stream.name,
                "has_draft": stream.has_draft,
                "offers": [],
            },
        )

        if link is not None:
            share = link.draft_share if stream.has_draft else link.published_share
            pinned = link.draft_pinned if stream.has_draft else link.published_pinned
            result["offers"].append(
                {
                    "id": offer.id,
                    "name": offer.name,
                    "share": 0 if share is None else share,
                    "removed": share is None,
                    "pinned": pinned if share is not None else False,
                }
            )

    return list(streams.values())

class StreamNotFound(Exception):
    pass


class OfferEditConflict(Exception):
    pass


def add_offer_to_draft(
    session: Session,
    campaign_id: int,
    stream_id: int,
    offer_id: int,
    offer_name: str,
) -> None:
    stream = session.get(Stream, stream_id)
    if stream is None or stream.campaign_id != campaign_id:
        raise StreamNotFound

    links = {
        link.offer_id: link
        for link in session.scalars(
            select(StreamOffer).where(StreamOffer.stream_id == stream_id)
        )
    }

    if not links:
        raise OfferEditConflict("Выбери поток, в который уже импортировали офферы")

    _start_draft(stream, list(links.values()))

    existing_link = links.get(offer_id)
    if existing_link is not None:
        if existing_link.draft_share is None:
            raise OfferEditConflict("Этот оффер можно вернуть через Bring Back")
        raise OfferEditConflict("Этот оффер уже есть в потоке")

    offer = session.get(Offer, offer_id)
    if offer is None:
        session.add(Offer(id=offer_id, name=offer_name))
        session.flush()
    else:
        offer.name = offer_name

    new_link = StreamOffer(
        stream_id=stream_id,
        offer_id=offer_id,
        draft_share=0,
        draft_pinned=False,
    )
    session.add(new_link)
    links[offer_id] = new_link

    _recalculate_draft_shares(list(links.values()))

def cancel_stream_draft(
    session: Session,
    campaign_id: int,
    stream_id: int,
) -> None:
    stream = session.get(Stream, stream_id)
    if stream is None or stream.campaign_id != campaign_id:
        raise StreamNotFound

    if not stream.has_draft:
        return

    links = session.scalars(
        select(StreamOffer).where(StreamOffer.stream_id == stream_id)
    )

    for link in links:
        if link.was_published:
            link.draft_share = None
            link.draft_pinned = False
        else:
            session.delete(link)

    stream.has_draft = False

def _start_draft(stream: Stream, links: list[StreamOffer]) -> None:
    if stream.has_draft:
        return

    for link in links:
        link.draft_share = link.published_share
        link.draft_pinned = link.published_pinned

    stream.has_draft = True


def _recalculate_draft_shares(links: list[StreamOffer]) -> None:
    active_links = [link for link in links if link.draft_share is not None]
    if not active_links:
        return

    pinned_shares = {
        link.offer_id: link.draft_share
        for link in active_links
        if link.draft_pinned and link.draft_share is not None
    }
    shares = distribute_shares(
        [link.offer_id for link in active_links],
        pinned_shares,
    )

    for link in active_links:
        link.draft_share = shares[link.offer_id]

class OfferLinkNotFound(Exception):
    pass


def set_draft_offer_active(
    session: Session,
    campaign_id: int,
    stream_id: int,
    offer_id: int,
    active: bool,
) -> None:
    stream = session.get(Stream, stream_id)
    if stream is None or stream.campaign_id != campaign_id:
        raise StreamNotFound

    links = {
        link.offer_id: link
        for link in session.scalars(
            select(StreamOffer).where(StreamOffer.stream_id == stream_id)
        )
    }
    link = links.get(offer_id)
    if link is None:
        raise OfferLinkNotFound

    current_share = link.draft_share if stream.has_draft else link.published_share
    if (current_share is not None) == active:
        return

    _start_draft(stream, list(links.values()))

    link.draft_share = 0 if active else None
    link.draft_pinned = False
    _recalculate_draft_shares(list(links.values()))

def set_draft_offer_pinned(
    session: Session,
    campaign_id: int,
    stream_id: int,
    offer_id: int,
    pinned: bool,
) -> None:
    stream = session.get(Stream, stream_id)
    if stream is None or stream.campaign_id != campaign_id:
        raise StreamNotFound

    link = session.get(StreamOffer, (stream_id, offer_id))
    if link is None:
        raise OfferLinkNotFound

    if stream.has_draft:
        share = link.draft_share
        current_pinned = link.draft_pinned
    else:
        share = link.published_share
        current_pinned = link.published_pinned

    if share is None:
        raise OfferEditConflict("Сначала верни оффер через Bring Back")

    if current_pinned == pinned:
        return

    if not stream.has_draft:
        links = list(
            session.scalars(
                select(StreamOffer).where(StreamOffer.stream_id == stream_id)
            )
        )
        _start_draft(stream, links)

    link.draft_pinned = pinned


class PublishedOffersMismatch(Exception):
    pass


def _active_offer_shares(remote_stream: dict) -> dict[int, int]:
    return {
        item["offer_id"]: item["share"]
        for item in (remote_stream.get("offers") or [])
        if item.get("state", "active") == "active"
    }

def publish_stream_draft(
    session: Session,
    campaign_id: int,
    stream_id: int,
    get_remote_stream: Callable[[int], dict],
    update_remote_offers: Callable[[int, list[dict]], dict],
) -> None:
    stream = session.get(Stream, stream_id)
    if stream is None or stream.campaign_id != campaign_id:
        raise StreamNotFound

    if not stream.has_draft:
        return

    links = list(
        session.scalars(
            select(StreamOffer)
            .where(StreamOffer.stream_id == stream_id)
            .order_by(StreamOffer.offer_id)
        )
    )
    published_shares = {
        link.offer_id: link.published_share
        for link in links
        if link.published_share is not None
    }
    draft_shares = {
        link.offer_id: link.draft_share
        for link in links
        if link.draft_share is not None
    }

    if draft_shares and sum(draft_shares.values()) != 100:
        raise OfferEditConflict("Доли активных офферов должны давать 100%")

    remote_stream = get_remote_stream(stream_id)
    if remote_stream["campaign_id"] != campaign_id:
        raise StreamNotFound

    remote_shares = _active_offer_shares(remote_stream)
    if remote_shares != draft_shares:
        if remote_shares != published_shares:
            raise OfferEditConflict(
                "Офферы потока изменились в Keitaro после последнего импорта"
            )

        payload = [
            {"offer_id": offer_id, "share": share, "state": "active"}
            for offer_id, share in draft_shares.items()
        ]
        payload.extend(
            {
                "offer_id": item["offer_id"],
                "share": item["share"],
                "state": "disabled",
            }
            for item in (remote_stream.get("offers") or [])
            if item.get("state") == "disabled"
            and item["offer_id"] not in draft_shares
        )

        updated_stream = update_remote_offers(stream_id, payload)
        if _active_offer_shares(updated_stream) != draft_shares:
            raise PublishedOffersMismatch

    for link in links:
        if link.draft_share is None and not link.was_published:
            session.delete(link)
            continue

        link.published_share = link.draft_share
        link.published_pinned = link.draft_pinned if link.draft_share is not None else False
        link.was_published = link.was_published or link.draft_share is not None
        link.draft_share = None
        link.draft_pinned = False

    stream.has_draft = False

