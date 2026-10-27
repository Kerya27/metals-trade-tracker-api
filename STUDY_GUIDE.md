# Study Guide

Plain-language tour of the project, so you can explain every part in an interview.

## 1. Project structure

```
app/
  main.py               Creates the FastAPI app, registers error handlers, mounts /api/v1
  core/
    config.py           Settings from env vars (pydantic-settings). get_settings() is cached.
    security.py         Argon2 password hashing, JWT create/decode
    errors.py           Domain exceptions + the ONE JSON error format + exception handlers
  db/
    base.py             SQLAlchemy DeclarativeBase + helper to store enums as strings
    session.py          Engine, SessionLocal, get_db() dependency (one session per request)
  models/               ORM tables: User, Supplier, Offer, Deal, DealStatusHistory, enums
  schemas/              Pydantic models: what the API accepts (Create/Update) and returns (Read)
  services/             Business logic. No HTTP here – just rules + DB work
    deal_state_machine.py   Allowed status transitions (pure Python, no DB)
  api/
    deps.py             Reusable dependencies: DbSession, CurrentUser, AdminUser
    v1/                 Routers (one file per resource) – thin, they only call services
alembic/                Migrations. versions/0001_initial_schema.py creates all tables + trigger
scripts/make_admin.py   CLI: promote an existing user to admin
tests/                  pytest suite; conftest.py sets up the test DB and fixtures
Dockerfile              Image for the API (runs migrations, then uvicorn)
docker-compose.yml      API + Postgres, API waits until Postgres is healthy
.github/workflows/ci.yml  Ruff + pytest with a Postgres service on every push
```

Why `models` vs `schemas`? Models = how data is stored (DB). Schemas = how data travels over
HTTP. Keeping them separate means you never accidentally return `hashed_password`.

## 2. Request flow: route → service → DB

Example `POST /api/v1/deals/7/transition {"status": "NEGOTIATION"}`:

1. **FastAPI** matches the route in `api/v1/deals.py` and validates the JSON body with the
   `DealTransitionRequest` schema. Bad body → `RequestValidationError` → 422 in our error format.
2. **Dependencies** run first: `get_db` opens a session; `get_current_user` reads the
   `Authorization: Bearer …` header, decodes the JWT, loads the user. Missing/bad token → 401.
3. The route calls `deal_service.transition_deal(db, 7, payload, user)`. That's all it does.
4. The **service**: loads the deal *only if the user may see it* (else 404), locks the row,
   checks the transition with the state machine (else 409), updates status, adds history, commits.
5. The route returns the ORM object; FastAPI converts it with `response_model=DealRead`.
6. `get_db` closes the session (rolling back anything not committed).

## 3. Auth, JWT and roles

- **Register**: password hashed with **Argon2** (slow on purpose, salted). We store only the hash.
  If the email is in `ADMIN_EMAILS`, role = `admin`, otherwise `trader`.
- **Login**: verify hash → issue a **JWT** signed with `JWT_SECRET` (HS256). Payload: `sub` (user id),
  `role`, `iat`, `exp`. If the user doesn't exist we still run a dummy hash check so response time
  doesn't reveal which emails are registered.
- **Each request**: `get_current_user` verifies signature + expiry, then loads the user from DB.
- **Roles**: `AdminUser` dependency → 403 for non-admins (supplier writes). Deal ownership is
  checked in the service: traders' queries get `WHERE created_by = :me`, so a foreign deal simply
  isn't found → 404.

## 4. Status machine and transaction

`ALLOWED_TRANSITIONS` maps each status to the set of statuses it may go to. `assert_transition`
raises `InvalidStatusTransitionError` (409) with the allowed list in the message.

In `transition_deal`:
```
SELECT ... FROM deals WHERE id = 7 [AND created_by = me] FOR UPDATE   -- lock the row
validate transition
UPDATE deals SET status = ...
INSERT INTO deal_status_history ...
COMMIT                                                                -- both or nothing
```
- `FOR UPDATE` stops two simultaneous requests from both moving DRAFT→X.
- One `commit()` means the status and its history row are saved together. If anything fails
  before commit, the session is rolled back – the test `test_status_change_and_history_are_one_transaction`
  proves it.
- A Postgres **trigger** blocks UPDATE/DELETE on `deal_status_history` → truly append-only.

## 5. Tests

- `conftest.py` forces `DATABASE_URL` to the test DB (`..._test`, refuses anything else), creates
  the DB if needed, runs Alembic `downgrade base` + `upgrade head` once, and **TRUNCATEs** all tables
  after each test, so tests are independent.
- `TestClient` (built on httpx) calls the app in-process – no server needed.
- Fixtures build data: `admin_token`, `trader_token`, `other_trader_token`, `make_supplier`,
  `make_offer`, `make_deal`.
- Real Postgres (not SQLite) because we rely on Postgres features: trigger, `FOR UPDATE`, `ILIKE`.

## 6. Docker and CI

- `Dockerfile`: python:3.12-slim, install pinned requirements, copy code, run as non-root,
  `CMD alembic upgrade head && uvicorn ...`.
- `docker-compose.yml`: `db` has a `pg_isready` healthcheck; `api` has
  `depends_on: condition: service_healthy`, so migrations don't run before Postgres is ready.
  Data persists in the `pgdata` volume (`docker compose down -v` wipes it).
- CI: GitHub Actions starts a Postgres 16 service container, installs deps, runs `ruff check`,
  `ruff format --check`, `pytest`.

## 7. Likely interview questions

1. **Why a service layer?** Routes handle HTTP; services hold rules. Rules can be reused (CLI,
   background jobs) and tested without HTTP, and routes stay readable.
2. **How do you guarantee status + history are consistent?** Same DB transaction, one commit,
   row lock with `SELECT FOR UPDATE`. Failure before commit → rollback of both.
3. **Why 404 instead of 403 for another trader's deal?** 403 would confirm the deal exists. 404
   leaks nothing.
4. **What's in your JWT and how is it validated?** `sub`, `role`, `iat`, `exp`; HS256 signature
   with a secret from env; expiry and required claims checked by PyJWT; then the user is loaded from DB.
5. **How would you log a user out / revoke tokens?** Short expiry + refresh tokens, or a denylist
   (e.g. Redis) of token IDs (`jti`), or a per-user `token_version` checked on each request.
6. **Why Argon2?** Memory-hard, salted, recommended by OWASP; slow enough to make brute force expensive.
7. **Why Decimal and not float for prices?** Floats can't represent 0.1 exactly; money needs exact
   arithmetic. DB uses `NUMERIC(14,2)`, JSON returns strings.
8. **How does pagination work and what's its weakness?** `limit/offset` + `total` count, with a
   tie-breaker sort on `id` for stable pages. Large offsets get slow → keyset (cursor) pagination.
9. **How do you prevent SQL injection in sorting/filtering?** Filters use bound parameters via the
   ORM; `sort` is a `Literal` whitelist mapped to real columns – user text never becomes SQL.
10. **How do migrations run in Docker?** The container command runs `alembic upgrade head` before
    uvicorn; compose waits for the DB healthcheck. In bigger setups: a separate migration job.
11. **Why test against Postgres and not SQLite?** Behaviour differs (locks, triggers, ILIKE, types);
    tests must match production.
12. **How are tests isolated?** Separate `_test` database, schema migrated once, tables truncated
    after every test.
13. **Sync or async SQLAlchemy – why sync?** Simpler; FastAPI runs sync routes in a thread pool.
    I'd go async for many slow concurrent I/O calls; DB-bound CRUD is fine sync.
14. **How do you handle errors consistently?** Domain exceptions with `status_code` + `code`;
    handlers for them, for validation errors, HTTP errors and unexpected exceptions all return
    `{"error": {"code", "message", "details"}}`. 500s are logged, details hidden from clients.
15. **What would you add next?** Refresh tokens, rate limiting on login, structured logging +
    request IDs, offer quantity reservation when deals are contracted, deal currency conversion,
    keyset pagination, and a deploy (e.g. Fly.io/Render) with a managed Postgres.
