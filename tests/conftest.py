"""Test setup.

Tests run against a SEPARATE Postgres database (TEST_DATABASE_URL, must end in "_test").
The database is created if missing, migrated with Alembic once per session,
and all tables are truncated after every test.
"""

import os
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://metals:metals@localhost:5432/metals_test"
)
# Must be set BEFORE the app (and its settings/engine) is imported.
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["JWT_SECRET"] = "test-secret-key-that-is-long-enough-123456"
os.environ["ADMIN_EMAILS"] = "admin@metals.cz"

from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

from alembic import command  # noqa: E402
from app.db.session import engine  # noqa: E402
from app.main import app  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TABLES = "deal_status_history, deals, offers, suppliers, users"
PASSWORD = "Str0ng-pass!"


def _ensure_test_database() -> None:
    url = make_url(TEST_DATABASE_URL)
    if not (url.database or "").endswith("_test"):
        raise RuntimeError("Refusing to run tests: TEST_DATABASE_URL database must end in '_test'")
    admin_engine = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        exists = conn.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": url.database}
        )
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    admin_engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def _database() -> Iterator[None]:
    _ensure_test_database()
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    cfg.attributes["configure_logger"] = False
    command.downgrade(cfg, "base")  # start from a clean schema every run
    command.upgrade(cfg, "head")
    yield
    engine.dispose()


@pytest.fixture(autouse=True)
def _clean_tables() -> Iterator[None]:
    yield
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE"))


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


# ---------- helpers ----------


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _register_and_login(client: TestClient, email: str) -> str:
    r = client.post("/api/v1/auth/register", json={"email": email, "password": PASSWORD})
    assert r.status_code == 201, r.text
    r = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture
def admin_token(client: TestClient) -> str:
    return _register_and_login(client, "admin@metals.cz")


@pytest.fixture
def trader_token(client: TestClient) -> str:
    return _register_and_login(client, "trader@metals.cz")


@pytest.fixture
def other_trader_token(client: TestClient) -> str:
    return _register_and_login(client, "other@metals.cz")


@pytest.fixture
def make_supplier(client: TestClient, admin_token: str) -> Callable[..., dict[str, Any]]:
    def _make(**overrides: Any) -> dict[str, Any]:
        body = {"name": "Zaporizhzhia Alu", "country": "UA", "contact_email": "sales@zalu.ua"}
        body.update(overrides)
        r = client.post("/api/v1/suppliers", json=body, headers=auth(admin_token))
        assert r.status_code == 201, r.text
        return r.json()

    return _make


@pytest.fixture
def make_offer(
    client: TestClient, make_supplier: Callable[..., dict[str, Any]], trader_token: str
) -> Callable[..., dict[str, Any]]:
    supplier_cache: dict[str, int] = {}

    def _make(token: str | None = None, **overrides: Any) -> dict[str, Any]:
        if "supplier_id" not in overrides and "id" not in supplier_cache:
            supplier_cache["id"] = make_supplier()["id"]
        body = {
            "supplier_id": supplier_cache.get("id"),
            "material": "aluminium dross",
            "quantity_tonnes": "100",
            "price_per_tonne": "300.00",
            "currency": "EUR",
            "incoterm": "FCA",
        }
        body.update(overrides)
        r = client.post("/api/v1/offers", json=body, headers=auth(token or trader_token))
        assert r.status_code == 201, r.text
        return r.json()

    return _make


@pytest.fixture
def make_deal(
    client: TestClient, make_offer: Callable[..., dict[str, Any]], trader_token: str
) -> Callable[..., dict[str, Any]]:
    def _make(token: str | None = None, **overrides: Any) -> dict[str, Any]:
        offer_id = overrides.pop("offer_id", None) or make_offer()["id"]
        body = {
            "offer_id": offer_id,
            "buyer_name": "Brno Foundry s.r.o.",
            "agreed_price_per_tonne": "295.00",
            "quantity_tonnes": "50",
        }
        body.update(overrides)
        r = client.post("/api/v1/deals", json=body, headers=auth(token or trader_token))
        assert r.status_code == 201, r.text
        return r.json()

    return _make
