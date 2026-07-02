# _root_infra — assessed 2026-07-02

Slice: main.py, auth.py, clients.py, config.py, crypto.py, db.py, disclaimer.py,
rate_limit.py, digest.py, Dockerfile, docker-compose.yml.

## Findings

- [SEV1] Dockerfile:34 — no `.dockerignore` exists and `COPY --chown=app:app . .`
  copies the entire build context into the image. If a `.env` is present at build
  time (developer machine, CI checkout) it is baked into an image layer that is
  pushed to `ghcr.io/reese8272/cfo-agent:latest` — Anthropic key, JWT secret,
  Fernet key, Postgres password leak in the registry (scale axis I: "no secret in
  image layers"). Also ships `.git/`, `tests/`, docs into the runtime image | fix:
  add a `.dockerignore` at repo root containing at minimum `.env`, `.env.*`,
  `!.env.example`, `.git`, `__pycache__`, `tests`, `*.pyc`, `docs`. Rebuild and
  confirm `docker history` shows no env layer.

- [SEV1] clients.py:56 — `AsyncAnthropic(api_key=...)` is constructed with **no
  `timeout`**, so it inherits the SDK default (600 s). `config.llm_timeout_seconds`
  (120) exists and is documented in `.env.example` but is never wired in. A slow /
  hung Anthropic response stalls agent requests for up to 10 minutes with no
  backpressure (scale axis E: "timeouts on every external call") | fix:
  `AsyncAnthropic(api_key=..., timeout=get_settings().llm_timeout_seconds,
  max_retries=2)`.

- [SEV1] crypto.py:26-30 — single-key `Fernet(...)`; no `MultiFernet` support, so
  the code cannot decrypt-with-old / encrypt-with-new. THREAT_MODEL §2 and
  `.env.example` both promise a key-rotation runbook, but rotation is
  operationally impossible without re-encrypting the whole vault offline (scale
  axis I: "code can decrypt with the old key while encrypting with the new") | fix:
  accept a comma-separated `VAULT_ENCRYPTION_KEYS`, build
  `MultiFernet([Fernet(k) for k in keys])` — first key encrypts, all keys decrypt;
  rotate by prepending the new key.

- [SEV2] rate_limit.py:8 — `Limiter(key_func=get_remote_address)` uses slowapi's
  default **in-memory** store: it is per-process (does not share across replicas)
  and fails open on restart, so the `10/minute` login and `3/hour` register limits
  reset on every deploy and are not enforced fleet-wide (scale axis F) | fix: pass
  `storage_uri=get_settings().redis_url` (Redis is already a dependency). Keyed by
  IP is acceptable for the pre-auth login/register routes.

- [SEV2] auth.py:113-118 — login is a username-enumeration timing oracle: when the
  user is absent, bcrypt is skipped (fast path); when present, `_verify_password`
  runs bcrypt (~100 ms). Response-time delta reveals whether a username exists |
  fix: always run a bcrypt verify against a fixed dummy hash when `user is None`,
  so both paths take equal time.

- [SEV2] main.py:59-64 — FastAPI is created without `docs_url`/`redoc_url`/
  `openapi_url` gating on env, so `/docs`, `/redoc`, `/openapi.json` are exposed in
  production (scale axis I: "/docs disabled in prod") | fix:
  `_prod = get_settings().env == "production"` then pass
  `docs_url=None if _prod else "/docs"`, same for `redoc_url` and `openapi_url`.

- [SEV2] Dockerfile:35 & docker-compose (app CMD) — `uvicorn main:app` runs with no
  `--timeout-graceful-shutdown`; on `docker compose up -d` redeploy, in-flight
  requests (including long agent/LLM calls) are killed abruptly | fix: append
  `--timeout-graceful-shutdown 30` to the uvicorn CMD.

- [SEV2] db.py:30-35 — pool math is not documented against replicas. `pool_size=5,
  max_overflow=5` = 10 connections/process; fine for single-replica v1, but there
  is no `pool_recycle` and no PgBouncer, so scaling past ~9 API replicas would
  approach Postgres `max_connections=100`. `pool_pre_ping=True` is set (good) |
  fix: add `pool_recycle=1800`; document the pool×replicas ≤ max_connections math
  in deployment docs before adding replicas (needs-load-confirmation).

- [SEV2] main.py:67-73 — CORS uses `allow_methods=["*"]`, `allow_headers=["*"]`
  with `allow_credentials=True`. Safe only while `allowed_origins` is an explicit
  list (default `["http://localhost:8000"]`), but the wildcard method/header combo
  is broad for a finance app | fix: narrow to the methods/headers actually used, or
  leave with a note; ensure the prod origin is set via `ALLOWED_ORIGINS`, never
  `*`.

- [cleanup] main.py — no security-response-headers middleware (HSTS,
  X-Content-Type-Options, X-Frame-Options). Behind Cloudflare Tunnel this is
  partially covered, but defense-in-depth is cheap | fix: add a small middleware
  or `secure` headers; low priority.

- [cleanup] disclaimer.py:18 — `get_disclaimer()` reads `os.environ` directly,
  duplicating `config.wealth_disclaimer_text` and bypassing the typed settings
  loader (DRY) | fix: read `get_settings().wealth_disclaimer_text or DISCLAIMER`.

- [cleanup] digest.py:124 — `_send_email_sync(subject, body, settings)` — the
  `settings` parameter is untyped | fix: annotate `settings: Settings`.

- [cleanup] config.py:25 — `vault_encryption_key: str = Field(..., min_length=1)`;
  a real Fernet key is a 44-char base64 string, so `min_length=1` will not fail
  fast on a truncated/garbage key (it only fails later at `Fernet(...)`) | fix:
  tighten to `min_length=44`.

## Rubric coverage
| Category | Status |
|---|---|
| 1 Resource lifecycle | ok — sessions via `async with`, engine/redis/anthropic singletons, SMTP via `asyncio.to_thread`, guaranteed close on shutdown |
| 2 Concurrency & scale | 3 findings — Anthropic no timeout, in-memory limiter, pool_recycle/replica math undocumented; bcrypt correctly off-loop via `run_in_threadpool`, SMTP off-loop |
| 3 Security & compliance | 4 findings — .env bakeable into image (SEV1), no key rotation (SEV1), /docs exposed, login timing oracle; no secrets in logs (verified), Fernet-at-rest good |
| 4 Domain correctness | n/a (infra slice; disclaimer helper present and applied in digest.py) |
| 5 LLM SDK | partial — client is a singleton but missing timeout; token logging / caching live in agent/ (out of slice) |
| 6 Cleanliness & typing | 3 cleanups — disclaimer DRY, untyped `settings` param, weak Fernet-key min_length |
| 7 Error handling / API | ok — /health degraded=503, rate-limit handler returns 429, auth returns 401/409, error messages safe |
| 8 Config & paths | ok — pydantic BaseSettings fail-fast, all keys in `.env.example`, static dir absolute via `Path(__file__)`; `llm_timeout_seconds` present but unused (see clients finding) |

## Module verdict
NEEDS-WORK — no cross-tenant/data-loss BLOCKER (single-user v1), but two SEV1
secret/compliance gaps (missing `.dockerignore` bakes secrets into a public
registry image; no Fernet key-rotation despite a promised runbook) and a missing
LLM timeout must be fixed before this goes public/portfolio.
