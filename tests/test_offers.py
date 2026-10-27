from tests.conftest import auth


def _ids(response) -> list[int]:
    return [o["id"] for o in response.json()["items"]]


def test_create_offer(client, make_supplier, trader_token):
    supplier = make_supplier()
    r = client.post(
        "/api/v1/offers",
        json={
            "supplier_id": supplier["id"],
            "material": "aluminium ingot",
            "quantity_tonnes": "25.5",
            "price_per_tonne": "2150.00",
            "currency": "USD",
            "incoterm": "CIF",
        },
        headers=auth(trader_token),
    )
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "ACTIVE"
    assert body["quantity_tonnes"] == "25.500"
    assert body["price_per_tonne"] == "2150.00"


def test_create_offer_for_missing_supplier_returns_404(client, trader_token):
    r = client.post(
        "/api/v1/offers",
        json={
            "supplier_id": 999,
            "material": "slag",
            "quantity_tonnes": "1",
            "price_per_tonne": "1",
            "currency": "EUR",
            "incoterm": "EXW",
        },
        headers=auth(trader_token),
    )
    assert r.status_code == 404


def test_create_offer_rejects_negative_price_and_bad_incoterm(client, make_supplier, trader_token):
    supplier = make_supplier()
    r = client.post(
        "/api/v1/offers",
        json={
            "supplier_id": supplier["id"],
            "material": "slag",
            "quantity_tonnes": "10",
            "price_per_tonne": "-5",
            "currency": "EUR",
            "incoterm": "XYZ",
        },
        headers=auth(trader_token),
    )
    assert r.status_code == 422
    fields = {d["loc"][-1] for d in r.json()["error"]["details"]}
    assert {"price_per_tonne", "incoterm"} <= fields


def test_filter_by_material_currency_and_status(client, make_offer, trader_token):
    dross = make_offer(material="Aluminium Dross", currency="EUR")
    make_offer(material="aluminium slag", currency="USD")
    closed = make_offer(material="aluminium dross", currency="EUR")
    client.patch(
        f"/api/v1/offers/{closed['id']}", json={"status": "CLOSED"}, headers=auth(trader_token)
    )

    r = client.get(
        "/api/v1/offers",
        params={"material": "dross", "currency": "EUR", "status": "ACTIVE"},
        headers=auth(trader_token),
    )
    assert r.status_code == 200
    assert _ids(r) == [dross["id"]]
    assert r.json()["total"] == 1


def test_filter_by_price_range(client, make_offer, trader_token):
    cheap = make_offer(price_per_tonne="100.00")
    mid = make_offer(price_per_tonne="250.00")
    make_offer(price_per_tonne="900.00")
    r = client.get(
        "/api/v1/offers",
        params={"min_price": "100", "max_price": "300", "sort": "price_per_tonne"},
        headers=auth(trader_token),
    )
    assert _ids(r) == [cheap["id"], mid["id"]]


def test_invalid_price_range_returns_422(client, trader_token):
    r = client.get(
        "/api/v1/offers",
        params={"min_price": "500", "max_price": "100"},
        headers=auth(trader_token),
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


def test_pagination_and_sorting(client, make_offer, trader_token):
    prices = ["500.00", "100.00", "300.00", "200.00", "400.00"]
    offers = {p: make_offer(price_per_tonne=p)["id"] for p in prices}

    r = client.get(
        "/api/v1/offers",
        params={"sort": "-price_per_tonne", "limit": 2, "offset": 1},
        headers=auth(trader_token),
    )
    body = r.json()
    assert body["total"] == 5
    assert body["limit"] == 2 and body["offset"] == 1
    assert _ids(r) == [offers["400.00"], offers["300.00"]]


def test_invalid_sort_field_rejected(client, trader_token):
    r = client.get("/api/v1/offers", params={"sort": "password"}, headers=auth(trader_token))
    assert r.status_code == 422


def test_other_trader_cannot_modify_offer_but_admin_can(
    client, make_offer, other_trader_token, admin_token
):
    offer = make_offer()
    url = f"/api/v1/offers/{offer['id']}"
    r = client.patch(url, json={"price_per_tonne": "1.00"}, headers=auth(other_trader_token))
    assert r.status_code == 403
    assert client.delete(url, headers=auth(other_trader_token)).status_code == 403

    r = client.patch(url, json={"price_per_tonne": "310.00"}, headers=auth(admin_token))
    assert r.status_code == 200
    assert r.json()["price_per_tonne"] == "310.00"


def test_cannot_delete_offer_with_deals(client, make_deal, trader_token):
    deal = make_deal()
    r = client.delete(f"/api/v1/offers/{deal['offer_id']}", headers=auth(trader_token))
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "offer_has_deals"
