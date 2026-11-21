class InvalidDistribution(ValueError):
    pass


def distribute_shares(
    offer_ids: list[int],
    pinned_shares: dict[int, int],
) -> dict[int, int]:
    remaining = 100 - sum(pinned_shares.values())
    unpinned = sorted(
        offer_id for offer_id in offer_ids if offer_id not in pinned_shares
    )

    if not unpinned:
        if remaining != 0:
            raise InvalidDistribution("Закреплённые доли должны давать 100%")
        return dict(pinned_shares)

    if remaining < len(unpinned):
        raise InvalidDistribution(
            "Освободи долю, чтобы каждому незакреплённому офферу достался хотя бы 1%"
        )

    base_share, extra = divmod(remaining, len(unpinned))
    shares = dict(pinned_shares)

    for position, offer_id in enumerate(unpinned):
        shares[offer_id] = base_share + int(position < extra)

    return shares