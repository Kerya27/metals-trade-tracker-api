# Metals Trade Tracker API

REST API for a metals trading desk: register **suppliers**, publish **offers** (aluminium dross,
slag, ingots…) and move **deals** through a controlled workflow
`DRAFT → NEGOTIATION → CONTRACTED → SHIPPED → CLOSED` (or `CANCELLED` before shipping),
with a tamper-proof status history.

Built as a portfolio project modelled on real commodity-trading work.

<!-- Screenshot placeholder: add docs/swagger-ui.png and put ![Swagger UI](docs/swagger-ui.png) here -->

## Stack

Python 3.12 · FastAPI · Pydantic v2 + pydantic-settings · SQLAlchemy 2.0 (typed ORM) · Alembic ·
PostgreSQL 16 · JWT (PyJWT) · Argon2 password hashing · pytest + httpx · Ruff · Docker Compose ·
GitHub Actions

## Run it (Docker)

```bash
git clone https://github.com/Kerya27/metals-trade-tracker-api.git
cd metals-trade-tracker-api
cp .env.example .env          # optional: works without it using dev defaults
docker compose up --build
```

Open **http://localhost:8000/docs**. Migrations run automatically on startup.

### Becoming admin

Two options (both documented in `.env.example`):

1. **Env variable** – emails listed in `ADMIN_EMAILS` (comma-separated) get the `admin` role when
   they register. Default for local Docker: `admin@example.cz`.
2. **Seed script** – promote an already registered user:
   ```bash
   docker compose exec api python -m scripts.make_admin you@example.cz
   ```

## Run the tests

Tests use a **separate database** (`metals_test`, created automatically) and never touch the dev DB.

```bash
docker compose up -d db
python -m venv .venv && source .venv/Scripts/activate   # Windows Git Bash; Linux/macOS: .venv/bin/activate
pip install -r requirements-dev.txt
ruff check . && pytest
```

51 tests cover auth, permissions, filters/pagination/sorting, the status machine, transaction
rollback, the append-only history trigger and the error format.

## Example requests

```bash
API=http://localhost:8000/api/v1

# register + login (admin@example.cz becomes admin via ADMIN_EMAILS)
curl -X POST $API/auth/register -H "Content-Type: application/json" \
  -d '{"email":"admin@example.cz","password":"Admin12345!"}'
TOKEN=$(curl -s -X POST $API/auth/login -H "Content-Type: application/json" \
  -d '{"email":"admin@example.cz","password":"Admin12345!"}' | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

# supplier (admin only)
curl -X POST $API/suppliers -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name":"Zaporizhzhia Alu Recycling","country":"UA","contact_email":"sales@zalu.ua"}'

# offer
curl -X POST $API/offers -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"supplier_id":1,"material":"aluminium dross","quantity_tonnes":"120","price_per_tonne":"310.00","currency":"EUR","incoterm":"FCA"}'

# filtered, sorted, paginated offers
curl "$API/offers?material=dross&currency=EUR&min_price=200&max_price=400&sort=-price_per_tonne&limit=10" \
  -H "Authorization: Bearer $TOKEN"

# deal + status change + history
curl -X POST $API/deals -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"offer_id":1,"buyer_name":"Brno Foundry s.r.o.","agreed_price_per_tonne":"300.00","quantity_tonnes":"60"}'
curl -X POST $API/deals/1/transition -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"status":"NEGOTIATION","comment":"Buyer asked for samples"}'
curl $API/deals/1/history -H "Authorization: Bearer $TOKEN"
```

Invalid transition example (`DRAFT → SHIPPED`) returns **409**:

```json
{"error": {"code": "invalid_status_transition",
  "message": "Cannot change deal status from DRAFT to SHIPPED. Allowed next statuses: CANCELLED, NEGOTIATION.",
  "details": {"from_status": "DRAFT", "to_status": "SHIPPED", "allowed": ["CANCELLED", "NEGOTIATION"]}}}
```

## Endpoints (`/api/v1`)

| Method | Path | Access |
|---|---|---|
| GET | `/health` | public |
| POST | `/auth/register` | public |
| POST | `/auth/login` | public → JWT |
| GET | `/auth/me` | authenticated |
| GET | `/suppliers`, `/suppliers/{id}` | authenticated |
| POST / PATCH / DELETE | `/suppliers`, `/suppliers/{id}` | admin |
| GET | `/offers` (filters: `material`, `status`, `currency`, `supplier_id`, `min_price`, `max_price`; `sort`, `limit`, `offset`) | authenticated |
| GET | `/offers/{id}` | authenticated |
| POST | `/offers` | authenticated |
| PATCH / DELETE | `/offers/{id}` | creator or admin |
| POST | `/deals` | authenticated |
| GET | `/deals` (filter: `status`; `limit`, `offset`) | own deals (admin: all) |
| GET | `/deals/{id}` | owner or admin (else 404) |
| POST | `/deals/{id}/transition` | owner or admin (else 404) |
| GET | `/deals/{id}/history` | owner or admin (else 404) |

Status codes: `401` not logged in · `403` not allowed · `404` not found / someone else's deal ·
`409` invalid transition or conflict · `422` validation. Every error uses one shape:
`{"error": {"code", "message", "details"}}`.

## Design decisions

- **Layers**: routes (HTTP only, thin) → services (business rules) → SQLAlchemy models.
  Services raise domain errors (`NotFoundError`, `InvalidStatusTransitionError`…) that one
  handler maps to HTTP status codes and the common JSON format.
- **Status machine** is a plain dict of allowed transitions (`app/services/deal_state_machine.py`),
  unit-tested for every pair of statuses.
- **One transaction per transition**: the deal row is locked with `SELECT … FOR UPDATE`, the status
  is updated and the history row inserted, then a single `COMMIT`. A test simulates a failure while
  writing history and checks that the status change was rolled back.
- **Append-only history** is enforced by a PostgreSQL trigger that rejects `UPDATE`/`DELETE`,
  not only by the absence of endpoints.
- **Foreign deals return 404, not 403**, so traders can't discover which deal IDs exist.
- **Money is `NUMERIC`/`Decimal`**, serialized as strings in JSON (`"310.00"`) to avoid float rounding.
- **Enums stored as VARCHAR + CHECK constraints** instead of native Postgres enums – easier to
  change in later migrations.
- **Sync SQLAlchemy** (FastAPI runs sync endpoints in a thread pool) – simpler, and plenty for this load.
- **JWT is stateless**, but the user is reloaded from the DB on each request, so role changes and
  deleted users take effect immediately.
- **Tests** run against real PostgreSQL (needed for the trigger and row locks), migrated with
  Alembic, so migrations are tested too.

### Assumptions (things the spec left open)

- Offers are a shared marketplace: every authenticated user can read them; any user can create
  one; only the creator or an admin can edit/delete. Offers with deals can't be deleted (close them).
- A deal's quantity can't exceed the offer quantity, and deals can only be opened on `ACTIVE` offers.
  Deals don't reduce the offer's quantity (no stock reservation).
- A deal uses the currency of its offer. `country` is an ISO 3166-1 alpha-2 code; `incoterm` is one
  of Incoterms 2020.
- Deal creation writes the first history row (`null → DRAFT`).
- Admins can transition any deal; there is no deal delete (audit trail).
