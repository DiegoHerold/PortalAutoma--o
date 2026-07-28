from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from modules.dispatch.domain.errors import InvalidOfferTransition, OfferSecurityError
from modules.dispatch.domain.offer import ExecutionOffer, ExecutionOfferStatus, RejectionCode
from modules.dispatch.domain.reservation import ResourceReservation
from modules.dispatch.domain.states import ResourceReservationStatus


def test_offer_accept_commit_lifecycle() -> None:
    now = datetime.utcnow()
    offer = ExecutionOffer.create(
        id="off_1",
        execution_attempt_id="att_1",
        agent_id="agt_1",
        agent_instance_id="agi_1",
        requirements_snapshot={"required_pools": ["background"]},
        offered_at=now,
        expires_at=now + timedelta(minutes=1),
    )

    committed = offer.accept(agent_id="agt_1", agent_instance_id="agi_1", now=now).commit(
        token_hash="abc",
        token_expires_at=now + timedelta(minutes=10),
        now=now,
    )

    assert committed.status == ExecutionOfferStatus.COMMITTED


def test_offer_rejects_wrong_agent_instance() -> None:
    now = datetime.utcnow()
    offer = ExecutionOffer.create(
        id="off_1",
        execution_attempt_id="att_1",
        agent_id="agt_1",
        agent_instance_id="agi_1",
        requirements_snapshot={},
        offered_at=now,
        expires_at=now + timedelta(minutes=1),
    )

    with pytest.raises(OfferSecurityError):
        offer.accept(agent_id="agt_1", agent_instance_id="agi_2", now=now)


def test_rejected_offer_cannot_be_committed() -> None:
    now = datetime.utcnow()
    offer = ExecutionOffer.create(
        id="off_1",
        execution_attempt_id="att_1",
        agent_id="agt_1",
        agent_instance_id="agi_1",
        requirements_snapshot={},
        offered_at=now,
        expires_at=now + timedelta(minutes=1),
    ).reject(
        agent_id="agt_1",
        agent_instance_id="agi_1",
        code=RejectionCode.AGENT_OVERLOADED,
        details={"load": 1},
        now=now,
    )

    with pytest.raises(InvalidOfferTransition):
        offer.commit(token_hash="abc", token_expires_at=now + timedelta(minutes=1), now=now)


def test_resource_reservation_can_convert_or_release() -> None:
    now = datetime.utcnow()
    reservation = ResourceReservation.create(
        id="res_1",
        execution_offer_id="off_1",
        execution_attempt_id="att_1",
        agent_id="agt_1",
        agent_instance_id="agi_1",
        pool_type="background",
        quantity=1,
        expires_at=now + timedelta(minutes=1),
        now=now,
    )

    assert reservation.status == ResourceReservationStatus.PENDING
    assert reservation.convert_to_usage(now).status == ResourceReservationStatus.ACTIVE
    assert reservation.release(now).status == ResourceReservationStatus.RELEASED
