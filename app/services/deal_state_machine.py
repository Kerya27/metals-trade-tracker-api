"""Deal status workflow.

DRAFT -> NEGOTIATION -> CONTRACTED -> SHIPPED -> CLOSED
CANCELLED is allowed from any state before SHIPPED.
CLOSED and CANCELLED are terminal.
"""

from app.core.errors import InvalidStatusTransitionError
from app.models.enums import DealStatus

ALLOWED_TRANSITIONS: dict[DealStatus, frozenset[DealStatus]] = {
    DealStatus.DRAFT: frozenset({DealStatus.NEGOTIATION, DealStatus.CANCELLED}),
    DealStatus.NEGOTIATION: frozenset({DealStatus.CONTRACTED, DealStatus.CANCELLED}),
    DealStatus.CONTRACTED: frozenset({DealStatus.SHIPPED, DealStatus.CANCELLED}),
    DealStatus.SHIPPED: frozenset({DealStatus.CLOSED}),
    DealStatus.CLOSED: frozenset(),
    DealStatus.CANCELLED: frozenset(),
}


def can_transition(current: DealStatus, new: DealStatus) -> bool:
    return new in ALLOWED_TRANSITIONS[current]


def assert_transition(current: DealStatus, new: DealStatus) -> None:
    if can_transition(current, new):
        return
    allowed = sorted(s.value for s in ALLOWED_TRANSITIONS[current])
    hint = f"Allowed next statuses: {', '.join(allowed)}." if allowed else "It is a final status."
    raise InvalidStatusTransitionError(
        f"Cannot change deal status from {current.value} to {new.value}. {hint}",
        details={"from_status": current.value, "to_status": new.value, "allowed": allowed},
    )
