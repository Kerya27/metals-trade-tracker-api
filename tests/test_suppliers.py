from tests.conftest import auth

SUPPLIER = {"name": "Kyiv Metals", "country": "ua", "contact_email": "info@kyivmetals.ua"}


def test_suppliers_require_authentication(client):
    assert client.get("/api/v1/suppliers").status_code == 401


def test_trader_cannot_create_supplier(client, trader_token):
    r = client.post("/api/v1/suppliers", json=SUPPLIER, headers=auth(trader_token))
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "forbidden"


def test_admin_crud_and_trader_can_read(client, admin_token, trader_token):
    r = client.post("/api/v1/suppliers", json=SUPPLIER, headers=auth(admin_token))
    assert r.status_code == 201
    supplier = r.json()
    assert supplier["country"] == "UA"  # normalized to upper case

    r = client.get("/api/v1/suppliers", headers=auth(trader_token))
    assert r.status_code == 200
    assert r.json()["total"] == 1

    r = client.patch(
        f"/api/v1/suppliers/{supplier['id']}",
        json={"name": "Kyiv Metals LLC"},
        headers=auth(admin_token),
    )
    assert r.status_code == 200
    assert r.json()["name"] == "Kyiv Metals LLC"

    r = client.delete(f"/api/v1/suppliers/{supplier['id']}", headers=auth(admin_token))
    assert r.status_code == 204
    r = client.get(f"/api/v1/suppliers/{supplier['id']}", headers=auth(trader_token))
    assert r.status_code == 404


def test_trader_cannot_update_or_delete_supplier(client, make_supplier, trader_token):
    supplier = make_supplier()
    url = f"/api/v1/suppliers/{supplier['id']}"
    assert client.patch(url, json={"name": "x"}, headers=auth(trader_token)).status_code == 403
    assert client.delete(url, headers=auth(trader_token)).status_code == 403


def test_cannot_delete_supplier_with_offers(client, make_offer, admin_token):
    offer = make_offer()
    r = client.delete(f"/api/v1/suppliers/{offer['supplier_id']}", headers=auth(admin_token))
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "supplier_has_offers"
