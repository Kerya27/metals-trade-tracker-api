from datetime import UTC, datetime, timedelta

import jwt

from tests.conftest import PASSWORD, auth


def test_health(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "database": "ok"}


def test_register_returns_trader_without_password(client):
    r = client.post(
        "/api/v1/auth/register", json={"email": "Kirill@Metals.cz", "password": PASSWORD}
    )
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "kirill@metals.cz"
    assert body["role"] == "trader"
    assert "password" not in body and "hashed_password" not in body


def test_register_duplicate_email_conflict(client):
    payload = {"email": "dup@metals.cz", "password": PASSWORD}
    client.post("/api/v1/auth/register", json=payload)
    r = client.post("/api/v1/auth/register", json=payload)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "email_taken"


def test_register_validation_error_uses_common_format(client):
    r = client.post("/api/v1/auth/register", json={"email": "not-an-email", "password": "short"})
    assert r.status_code == 422
    error = r.json()["error"]
    assert error["code"] == "validation_error"
    fields = {tuple(d["loc"])[-1] for d in error["details"]}
    assert {"email", "password"} <= fields


def test_admin_email_from_env_gets_admin_role(client, admin_token):
    r = client.get("/api/v1/auth/me", headers=auth(admin_token))
    assert r.status_code == 200
    assert r.json()["role"] == "admin"


def test_login_and_me(client, trader_token):
    r = client.get("/api/v1/auth/me", headers=auth(trader_token))
    assert r.status_code == 200
    assert r.json()["email"] == "trader@metals.cz"


def test_login_wrong_password(client, trader_token):
    r = client.post(
        "/api/v1/auth/login", json={"email": "trader@metals.cz", "password": "wrong-pass"}
    )
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "invalid_credentials"


def test_login_unknown_user_same_error(client):
    r = client.post("/api/v1/auth/login", json={"email": "ghost@metals.cz", "password": PASSWORD})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "invalid_credentials"


def test_me_requires_token(client):
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"
    assert r.headers["www-authenticate"] == "Bearer"


def test_me_rejects_garbage_token(client):
    r = client.get("/api/v1/auth/me", headers=auth("not.a.jwt"))
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "invalid_token"


def test_me_rejects_expired_token(client, trader_token):
    from app.core.config import get_settings

    settings = get_settings()
    user_id = jwt.decode(trader_token, settings.jwt_secret, algorithms=["HS256"])["sub"]
    past = datetime.now(UTC) - timedelta(hours=2)
    expired = jwt.encode(
        {"sub": user_id, "iat": past, "exp": past + timedelta(minutes=1)},
        settings.jwt_secret,
        algorithm="HS256",
    )
    r = client.get("/api/v1/auth/me", headers=auth(expired))
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "token_expired"


def test_unknown_route_uses_common_error_format(client):
    r = client.get("/api/v1/does-not-exist")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"
