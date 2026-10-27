import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.db.session import engine
from app.main import app
from app.services import deal_service
from tests.conftest import auth


def _transition(client, token, deal_id, status, comment=None):
    return client.post(
        f"/api/v1/deals/{deal_id}/transition",
        json={"status": status, "comment": comment},
        headers=auth(token),
    )


def test_create_deal_starts_in_draft_with_history(client, make_deal, trader_token):
    deal = make_deal()
    assert deal["status"] == "DRAFT"

    r = client.get(f"/api/v1/deals/{deal['id']}/history", headers=auth(trader_token))
    assert r.status_code == 200
    history = r.json()
    assert len(history) == 1
    assert history[0]["from_status"] is None
    assert history[0]["to_status"] == "DRAFT"


def test_deal_on_closed_offer_conflict(client, make_offer, trader_token):
    offer = make_offer()
    client.patch(
        f"/api/v1/offers/{offer['id']}", json={"status": "CLOSED"}, headers=auth(trader_token)
    )
    r = client.post(
        "/api/v1/deals",
        json={
            "offer_id": offer["id"],
            "buyer_name": "X",
            "agreed_price_per_tonne": "1",
            "quantity_tonnes": "1",
        },
        headers=auth(trader_token),
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "offer_not_active"


def test_deal_quantity_cannot_exceed_offer(client, make_offer, trader_token):
    offer = make_offer(quantity_tonnes="10")
    r = client.post(
        "/api/v1/deals",
        json={
            "offer_id": offer["id"],
            "buyer_name": "X",
            "agreed_price_per_tonne": "1",
            "quantity_tonnes": "10.001",
        },
        headers=auth(trader_token),
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "business_rule_violation"


def test_full_happy_path_and_history(client, make_deal, trader_token):
    deal = make_deal()
    for status in ["NEGOTIATION", "CONTRACTED", "SHIPPED", "CLOSED"]:
        r = _transition(client, trader_token, deal["id"], status, f"to {status}")
        assert r.status_code == 200, r.text
        assert r.json()["status"] == status

    history = client.get(f"/api/v1/deals/{deal['id']}/history", headers=auth(trader_token)).json()
    assert [(h["from_status"], h["to_status"]) for h in history] == [
        (None, "DRAFT"),
        ("DRAFT", "NEGOTIATION"),
        ("NEGOTIATION", "CONTRACTED"),
        ("CONTRACTED", "SHIPPED"),
        ("SHIPPED", "CLOSED"),
    ]
    assert history[-1]["comment"] == "to CLOSED"


def test_invalid_transition_returns_409_with_clear_message(client, make_deal, trader_token):
    deal = make_deal()
    r = _transition(client, trader_token, deal["id"], "SHIPPED")
    assert r.status_code == 409
    error = r.json()["error"]
    assert error["code"] == "invalid_status_transition"
    assert "from DRAFT to SHIPPED" in error["message"]
    assert error["details"]["allowed"] == ["CANCELLED", "NEGOTIATION"]


def test_cancel_allowed_before_shipped(client, make_deal, trader_token):
    deal = make_deal()
    _transition(client, trader_token, deal["id"], "NEGOTIATION")
    _transition(client, trader_token, deal["id"], "CONTRACTED")
    r = _transition(client, trader_token, deal["id"], "CANCELLED", "buyer withdrew")
    assert r.status_code == 200
    assert r.json()["status"] == "CANCELLED"
    # terminal state
    assert _transition(client, trader_token, deal["id"], "NEGOTIATION").status_code == 409


def test_cancel_not_allowed_after_shipped(client, make_deal, trader_token):
    deal = make_deal()
    for status in ["NEGOTIATION", "CONTRACTED", "SHIPPED"]:
        _transition(client, trader_token, deal["id"], status)
    r = _transition(client, trader_token, deal["id"], "CANCELLED")
    assert r.status_code == 409


def test_unknown_status_value_is_validation_error(client, make_deal, trader_token):
    deal = make_deal()
    r = _transition(client, trader_token, deal["id"], "TELEPORTED")
    assert r.status_code == 422


def test_trader_gets_404_for_foreign_deal(client, make_deal, other_trader_token):
    deal = make_deal()
    base = f"/api/v1/deals/{deal['id']}"
    headers = auth(other_trader_token)
    assert client.get(base, headers=headers).status_code == 404
    assert client.get(f"{base}/history", headers=headers).status_code == 404
    assert _transition(client, other_trader_token, deal["id"], "NEGOTIATION").status_code == 404


def test_trader_lists_only_own_deals_admin_sees_all(
    client, make_deal, trader_token, other_trader_token, admin_token
):
    mine = make_deal()
    theirs = make_deal(token=other_trader_token)

    r = client.get("/api/v1/deals", headers=auth(trader_token))
    assert [d["id"] for d in r.json()["items"]] == [mine["id"]]

    r = client.get("/api/v1/deals", headers=auth(admin_token))
    assert {d["id"] for d in r.json()["items"]} == {mine["id"], theirs["id"]}
    assert r.json()["total"] == 2


def test_admin_can_transition_any_deal(client, make_deal, admin_token):
    deal = make_deal()
    r = _transition(client, admin_token, deal["id"], "NEGOTIATION")
    assert r.status_code == 200


def test_list_deals_filter_by_status(client, make_deal, trader_token):
    a = make_deal()
    make_deal()
    _transition(client, trader_token, a["id"], "NEGOTIATION")
    r = client.get("/api/v1/deals", params={"status": "NEGOTIATION"}, headers=auth(trader_token))
    assert [d["id"] for d in r.json()["items"]] == [a["id"]]


def test_deals_require_authentication(client):
    assert client.get("/api/v1/deals").status_code == 401


def test_status_change_and_history_are_one_transaction(
    client, make_deal, trader_token, monkeypatch
):
    """If writing the history row fails, the status change must be rolled back too."""
    deal = make_deal()

    def broken_history(db, *args, **kwargs):
        db.flush()  # status UPDATE has already been sent to the DB at this point
        raise RuntimeError("simulated failure while writing history")

    monkeypatch.setattr(deal_service, "_record_history", broken_history)
    with TestClient(app, raise_server_exceptions=False) as c:
        r = _transition(c, trader_token, deal["id"], "NEGOTIATION")
    assert r.status_code == 500
    assert r.json()["error"]["code"] == "internal_error"

    monkeypatch.undo()
    r = client.get(f"/api/v1/deals/{deal['id']}", headers=auth(trader_token))
    assert r.json()["status"] == "DRAFT"
    history = client.get(f"/api/v1/deals/{deal['id']}/history", headers=auth(trader_token)).json()
    assert len(history) == 1


def test_history_is_append_only_in_database(make_deal):
    make_deal()
    with pytest.raises(DBAPIError, match="append-only"), engine.begin() as conn:
        conn.execute(text("UPDATE deal_status_history SET comment = 'tampered'"))
    with pytest.raises(DBAPIError, match="append-only"), engine.begin() as conn:
        conn.execute(text("DELETE FROM deal_status_history"))
