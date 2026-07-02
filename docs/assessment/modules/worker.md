# worker — assessed 2026-07-02

Slice: `worker/cron.py` (`worker/__init__.py` is empty). The scheduler delegates
the actual work to `digest.generate_and_send_digest()` (root module, owned by
another slice) — findings about the send/SMTP/idempotency *body* belong there;
here I assess the scheduling substrate and where cron fails to provide a guard.

## Findings
- [SEV1] worker/cron.py:44,67-71 — the weekly digest is scheduled on an in-process
  `AsyncIOScheduler` started in `main.py` lifespan (`start_scheduler()`), with NO
  leader election / distributed lock and NO idempotency guard on the send. This is
  fine on the documented single-container Docker-Compose deploy, but the moment the
  app runs 2+ replicas EVERY replica's scheduler fires `_run_weekly_digest`
  independently → each user gets N duplicate digest emails per Monday (scale axis C:
  at-least-once effectively becomes at-least-once-per-replica). fix: guard the send
  with a stable idempotency key, e.g. `INSERT INTO processed_jobs(job_key) VALUES
  ('digest:'||to_char(now(),'IYYY-IW')) ON CONFLICT DO NOTHING` and only send when
  the insert affected a row; or run the scheduler under a single-owner lease
  (Redis `SET lock NX EX`) so only one replica fires. Add a test that invokes the
  job twice and asserts one send. (needs-runtime-confirmation of target replica count.)
- [SEV2] worker/cron.py:45-53 — the cron job sets no `misfire_grace_time` and no
  `coalesce`. APScheduler's default `misfire_grace_time` is 1 second, so if the
  event loop is busy at 07:00:00 UTC for >1s (deploy, GC, a slow request) the
  weekly digest MISFIRES and is silently skipped for the entire week, with no
  operator signal. fix: `add_job(..., misfire_grace_time=3600, coalesce=True)` so a
  brief hiccup or a restart within the hour still fires exactly once. Consider a
  persistent jobstore if missed-run recovery across restarts is required.
- [SEV2] worker/cron.py:19-24 — `_run_weekly_digest` awaits
  `generate_and_send_digest()` with no timeout (scale axis E / backpressure). If the
  downstream LLM or SMTP call hangs, this job hangs indefinitely and never releases;
  the `except Exception` only catches errors, not a hang. fix: bound it —
  `await asyncio.wait_for(generate_and_send_digest(), timeout=300)` — and rely on /
  verify that digest.py sets per-call timeouts on its Anthropic + SMTP calls.
- [cleanup] worker/cron.py:35 — `httpx.AsyncClient(timeout=10)` is constructed fresh
  on every 5-minute ping instead of being a module-level singleton (rubric 1:
  external clients as singletons). Cost is negligible at this cadence, but the
  idiom is inconsistent. fix: hoist a module-level `_http = httpx.AsyncClient(
  timeout=10)` and reuse it (closed in `stop_scheduler`). Timeout itself is correct.

## Rubric coverage
| Category | Status |
|---|---|
| 1 Resource lifecycle | 1 finding — per-call httpx client (cleanup); no DB/SMTP opened here, singleton scheduler ok |
| 2 Concurrency & scale | 1 finding — SEV1 multi-replica double-fire (axis C); no blocking sync call in async (httpx async + timeout, all awaits) |
| 3 Security & compliance | ok — no secrets/PII logged (`exc` messages only, no balances/tokens); no SQL here |
| 4 Domain correctness | n/a (scheduler substrate; digest content owned by digest.py) |
| 5 LLM SDK | n/a (no LLM call in this module; delegated to digest.py) |
| 6 Cleanliness & typing | ok — every signature typed; deferred `import digest` is deliberate (circular-import avoidance) |
| 7 Error handling / API | n/a (not a router; both jobs catch+log, degrade gracefully) |
| 8 Config & paths | ok — `healthcheck_ping_url` typed in config.py:46 and documented in .env.example; no paths |

## Module verdict
NEEDS-WORK — clean and correct on a single replica, but the weekly digest has no
idempotency guard or misfire grace, so it double-sends under multi-replica deploy
and silently skips a week on a momentary loop stall; both need a fix before scale-out.
