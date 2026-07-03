# _root_infra — assessed 2026-07-03

Slice: `auth.py`, `clients.py`, `config.py`, `crypto.py`, `db.py`, `digest.py`,
`disclaimer.py`, `main.py`, `rate_limit.py`. This is the infra spine; recent
hardening work (MultiFernet rotation, `/docs` prod gate, graceful shutdown,
timing-safe login, security-headers middleware, `pool_recycle`) is present and
verified below — none of it re-flagged as missing.

## Findings

- [SEV2] disclaimer.py:18 — `get_disclaimer()` reads the override via
  `os.environ.get("WEALTH_DISCLAIMER_TEXT")`, but `config.Settings` already
  declares `wealth_disclaimer_text` (config.py:49) and `.env.example:55`
  documents it as a settable key. pydantic-settings loads `.env` into the
  `Settings` object **without** exporting to `os.environ`, so an operator who
  sets `WEALTH_DISCLAIMER_TEXT` in `.env` (the documented mechanism) gets it
  loaded into `Settings` but `os.environ.get` returns `None` — the override
  silently no-ops. Two sources of truth for one value. | fix: make
  `get_disclaimer()` return `get_settings().wealth_disclaimer_text or DISCLAIMER`
  and drop the `os` import; single source of truth, works from `.env`.

- [SEV2] digest.py:131 — `smtplib.SMTP(settings.smtp_host, settings.smtp_port)`
  is opened with no `timeout`. On a wedged/blackholed SMTP host the call blocks
  forever; it runs via `asyncio.to_thread`, so it won't stall the event loop,
  but the worker thread hangs indefinitely (and the `/digest/run-now` request
  awaiting it never returns). | fix: pass an explicit timeout,
  `smtplib.SMTP(host, port, timeout=30)`; the `with` block already guarantees
  close.

- [cleanup] digest.py:122 — `_send_email_sync(subject, body, settings)`: the
  `settings` parameter is untyped (rubric 6). | fix: annotate `settings: Settings`
  (import from `config`); return type `-> None` is already present.

- [cleanup] main.py:60,72 — `get_settings()` is called twice at module import
  (once for `_prod`, once for `settings`). Harmless (lru_cached) but reads as an
  oversight. | fix: bind `settings = get_settings()` once above line 60 and
  derive `_prod = settings.env == "production"` from it.

- [cleanup] auth.py:127 — failed-login logs the attempted username
  (`logger.warning("failed login attempt for username=%r", form.username)`).
  Standard-ish for audit, but it records arbitrary attacker-supplied input at
  WARNING; for a single-user app the only valid username is the owner's, so the
  value carries little signal. | fix: log the event without echoing the raw
  username (or truncate). Low priority.

## Verified-good (hardening landed, not defects)

- crypto.py:27 — `MultiFernet` rotation is correct: first key encrypts, any key
  decrypts; `InvalidToken` wrapped in `FernetDecryptionError` with no ciphertext
  or key material in the message. `@lru_cache(maxsize=1)` is safe (keys are
  process-static).
- auth.py:70,123 — timing-safe login confirmed: a fixed `_DUMMY_PASSWORD_HASH`
  is verified when the user is absent, and bcrypt runs on every path via
  `run_in_threadpool`, so absent-user and wrong-password take the same time.
  Register-once (auth.py:96) returns 409 after the first user. JWT carries
  `iat`/`exp`; decode catches `PyJWTError`/`ValueError` → 401.
- db.py:30 — engine singleton with `pool_pre_ping`, `pool_size=5`,
  `max_overflow=5`, `pool_recycle=1800`; `get_session` is a context-managed
  dependency that rolls back on exception and always closes; `dispose_engine`
  tears down on shutdown.
- clients.py — Redis and Anthropic are module-level lazy singletons; Anthropic
  client sets explicit `timeout` + `max_retries` from typed settings (avoids the
  600s SDK default); `ping_redis` swallows and logs failures.
- config.py — required secrets use `Field(..., min_length=…)` (fail-fast);
  `vault_encryption_key` min_length 44 catches a truncated Fernet key;
  `jwt_secret_key` min_length 32. Model ids sourced from settings
  (`claude-sonnet-4-6`, `claude-haiku-4-5-20251001` — both current/valid), not
  hardcoded in nodes. `get_settings() -> Settings` typed and `@lru_cache`d.
- main.py — lifespan brings up engine/redis/scheduler and tears them down in
  reverse on shutdown; `security_headers` sets `X-Content-Type-Options`,
  `X-Frame-Options: DENY`, `Referrer-Policy`, and prod-only HSTS; `/docs`,
  `/redoc`, `/openapi.json` are `None` in production; `/health` returns 503 +
  `status:"degraded"` when postgres or redis is down, 200 otherwise; static dir
  resolved absolutely via `Path(__file__).parent`.
- rate_limit.py — Redis-backed slowapi limiter (survives restarts), disabled
  under `TESTING`; storage URI from settings.
- Config/paths (rubric 8): every new key is present in `.env.example` with a
  description (`WEALTH_DISCLAIMER_TEXT` at line 55, SMTP block, `RENTCAST_API_KEY`,
  etc.); all filesystem paths are absolute.

## Rubric coverage
| Category | Status |
|---|---|
| 1 Resource lifecycle | ok — engine/redis/anthropic singletons, guaranteed session close, clean shutdown |
| 2 Concurrency & scale | 1 finding (SMTP no timeout); blocking SMTP correctly offloaded via to_thread |
| 3 Security & compliance | ok — rotation, timing-safe login, no secret in logs; 1 low-pri username-log cleanup; multi-tenant isolation correctly deferred (Road A) |
| 4 Domain correctness | 1 finding (disclaimer override no-op); digest embeds the mandatory disclaimer |
| 5 LLM SDK | ok — model id from settings, timeout+retries set (caching/token-logging live in agent nodes, out of slice) |
| 6 Cleanliness & typing | 2 cleanups (untyped `settings` param, double `get_settings()`) |
| 7 Error handling / API | ok — health 200/503, auth 401/409, rate-limit 429, safe messages |
| 8 Config & paths | ok — fail-fast typed settings, full `.env.example` coverage, absolute paths |

## Module verdict
NEEDS-WORK — no blockers or sev1; two SEV2s (disclaimer `.env` override silently
no-ops; SMTP call has no timeout) plus minor cleanups. The hardening spine
(rotation, timing-safe auth, graceful shutdown, security headers, prod `/docs`
gate) is solid and senior-grade.
