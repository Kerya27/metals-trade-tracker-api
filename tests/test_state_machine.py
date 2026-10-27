import pytest

from app.core.errors import InvalidStatusTransitionError
from app.models.enums import DealStatus as S
from app.services.deal_state_machine import ALLOWED_TRANSITIONS, assert_transition, can_transition

VALID = [
    (S.DRAFT, S.NEGOTIATION),
    (S.NEGOTIATION, S.CONTRACTED),
    (S.CONTRACTED, S.SHIPPED),
    (S.SHIPPED, S.CLOSED),
    (S.DRAFT, S.CANCELLED),
    (S.NEGOTIATION, S.CANCELLED),
    (S.CONTRACTED, S.CANCELLED),
]


@pytest.mark.parametrize(("current", "new"), VALID)
def test_valid_transitions(current, new):
    assert can_transition(current, new)
    assert_transition(current, new)  # does not raise


def test_every_other_transition_is_rejected():
    for current in S:
        for new in S:
            if (current, new) in VALID:
                continue
            assert not can_transition(current, new)
            with pytest.raises(InvalidStatusTransitionError):
                assert_transition(current, new)


def test_terminal_states_have_no_exits():
    assert ALLOWED_TRANSITIONS[S.CLOSED] == frozenset()
    assert ALLOWED_TRANSITIONS[S.CANCELLED] == frozenset()
