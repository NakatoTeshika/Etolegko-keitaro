from typing import Optional

from sqlalchemy import CheckConstraint, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Stream(Base):
    __tablename__ = "streams"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    campaign_id: Mapped[int] = mapped_column(index=True)
    name: Mapped[str]
    has_draft: Mapped[bool] = mapped_column(default=False)


class Offer(Base):
    __tablename__ = "offers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    name: Mapped[str]


class StreamOffer(Base):
    __tablename__ = "stream_offers"
    __table_args__ = (
        CheckConstraint(
            "published_share BETWEEN 0 AND 100",
            name="ck_stream_offers_published_share_range",
        ),
        CheckConstraint(
            "draft_share BETWEEN 0 AND 100",
            name="ck_stream_offers_draft_share_range",
        ),
    )

    stream_id: Mapped[int] = mapped_column(
        ForeignKey("streams.id", name="fk_stream_offers_stream"),
        primary_key=True,
    )
    offer_id: Mapped[int] = mapped_column(
        ForeignKey("offers.id", name="fk_stream_offers_offer"),
        primary_key=True,
    )

    published_share: Mapped[Optional[int]]
    draft_share: Mapped[Optional[int]]
    published_pinned: Mapped[bool] = mapped_column(default=False)
    draft_pinned: Mapped[bool] = mapped_column(default=False)
    was_published: Mapped[bool] = mapped_column(default=False)