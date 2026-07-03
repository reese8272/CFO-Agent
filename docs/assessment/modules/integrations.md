# integrations — assessed 2026-07-03

Slice: `integrations/market_data.py`, `integrations/property_data.py`,
`integrations/csv_import.py`, `integrations/__init__.py` (empty).

Headline: this is the highest-risk layer for blocking-calls-in-async, and it is
handled correctly. Every synchronous external call is offloaded off the event
loop — `fetch_price_async` wraps `fetch_price` in `asyncio.to_thread` +
`wait_for` (market_data.py:35); `parse_csv`/`parse_ofx` run via `to_thread`
(routers/imports.py:41,44); `fetch_property_estimate` runs via `to_thread`
(routers/vault.py:512). No blocking HTTP / `time.sleep` / blocking file read
executes on the loop thread. HTTP timeouts are present on every real network
call (market_data.py:78 =10s, property_data.py:48 =15s, yfinance bounded by the
15s `wait_for`). API keys are deliberately kept out of logs. In-memory work is
bounded (MAX_ROWS=50k + 10MB upload cap). The findings below are hardening and
polish, not outages.

## Findings

- [SEV2] integrations/market_data.py:35 — `asyncio.wait_for(asyncio.to_thread(fetch_price, ...), timeout)`
  bounds the *coroutine*, but a `to_thread` worker cannot be cancelled: when
  `wait_for` fires, the thread running `fetch_price` keeps executing until
  yfinance returns/errors. `fast_info` (market_data.py:60) sets no HTTP timeout
  of its own, so a genuinely hung Yahoo endpoint leaks a worker from the default
  `ThreadPoolExecutor` (bounded at `min(32, cpu+4)`). Enough concurrent hung
  fetches could drain that pool and stall *all* `to_thread` work app-wide
  (imports, property AVM). (needs-runtime-confirmation — unlikely to bite one
  user, but a real leak). | fix: give yfinance a timeout-bearing session
  (`yf.Ticker(ticker, session=_yf_session)` with a module-level
  `requests.Session` that enforces a connect/read timeout), or wrap
  `fetch_price_async` in a module-level `asyncio.Semaphore` so a stuck upstream
  can't exhaust the executor.

- [SEV2] integrations/csv_import.py:113,117-124 — `parse_ofx` feeds untrusted
  upload bytes to `ofxtools.Parser.OFXTree` (stdlib ElementTree underneath) with
  no XML-entity hardening. OFX/QFX is XML, so this is exposed to
  entity-expansion ("billion laughs") style DoS on the parse thread (rubric 3,
  external-data / untrusted input). Bounded today by the 10MB upload cap
  (routers/imports.py:31-35) and a single authenticated owner, so blast radius
  is small. (needs-runtime-confirmation). | fix: `pip install defusedxml` and
  either parse with a defused parser or set `defusedxml.defuse_stdlib()` before
  `OFXTree().parse(...)`; add a one-line pinned entry to requirements.txt.

- [SEV2] integrations/market_data.py:1,58 — yfinance sources prices by scraping
  Yahoo Finance, whose TOS prohibits redistribution/commercial use (rubric 3,
  external-data TOS). Fine for single-user personal use, but load-bearing for
  the "portfolio showcase" framing and for any future second user. | fix: add a
  one-line TOS note to the module docstring and to `docs/DECISIONS.md` /
  `docs/THREAT_MODEL.md` stating yfinance is personal-use-only and the licensed
  Alpha Vantage path is what a shared deployment would use.

- [cleanup] integrations/property_data.py:43 — uses a fresh `requests.get(...)`
  per call, while the sibling `market_data.py:23` pools via a module-level
  `_session = requests.Session()`. Inconsistent with the module's own
  established pattern (rubric 1). Volume is low (50 calls/month) so no real perf
  cost, but it reads as unpolished next to market_data. | fix: add
  `_session = requests.Session()` at module level and call `_session.get(...)`.

- [cleanup] integrations/csv_import.py:152 / routers/imports.py:13,71 —
  `_apply_mappings_raw` is underscore-prefixed (signals module-private) yet is
  imported and called across the module boundary by the router, i.e. it is
  actually public API (rubric 6, naming/API clarity). | fix: rename to
  `apply_mappings` and update the single import in routers/imports.py.

- [cleanup] integrations/csv_import.py:23,36,152 — bare generic annotations:
  `ParsedRow.raw: dict`, `_parse_amount(row: dict)`, and
  `_apply_mappings_raw(..., mappings: list)`; the `list` element type is
  meaningful (objects exposing `.pattern`/`.category`) (rubric 6, typing). |
  fix: `raw: dict[str, str]`; `row: dict[str, str]`; define a
  `class _Mapping(Protocol): pattern: str; category: str` and annotate
  `mappings: list[_Mapping]`.

- [cleanup] integrations/market_data.py:65 / property_data.py:66 — broad
  `except Exception` swallowing all errors and returning `None`. Intentional
  fail-soft (graceful per-provider degradation, which is the right call here),
  but it also masks programming errors. (rubric 6). | fix: leave the fail-soft
  behavior, but narrow to `except (requests.RequestException, ValueError,
  KeyError, InvalidOperation)` so a genuine bug surfaces instead of silently
  returning `None`.

## Rubric coverage
| Category | Status |
|---|---|
| 1 Resource lifecycle | 1 finding — property_data unpooled session (cleanup); market_data pools; CSV `StringIO`/`BytesIO` handles are GC-bounded; to_thread offload correct on all three sync entry points |
| 2 Concurrency & scale | 1 finding — to_thread thread-leak on hung yfinance (SEV2, needs-runtime-confirmation); otherwise correct — no blocking call on loop, MAX_ROWS=50k + 10MB upload cap bound memory, per-ticker isolation returns None on failure |
| 3 Security & compliance | 2 findings — OFX XML entity-expansion hardening (SEV2), yfinance/Yahoo TOS (SEV2); keys never logged (explicit guard comments market_data.py:72-73), no PII in logs, public price data unencrypted by design |
| 4 Domain correctness | ok — AVM disclaimer constant present + enforced at router (property_data.py:22-25); bank debit/credit sign convention correct (csv_import.py:56); parenthetical-negative handling correct (:45-47) |
| 5 LLM SDK | n/a (no LLM in this module) |
| 6 Cleanliness & typing | 3 findings — `_apply_mappings_raw` naming, generic annotations, broad excepts (all cleanup); no TODO/debug/commented-out code |
| 7 Error handling / API | n/a (library module; HTTP status mapping lives in the routers) |
| 8 Config & paths | ok — `rentcast_api_key`/`alpha_vantage_key` typed-optional in config.py:53-54, documented in .env.example:63-69; no hardcoded paths |

## Module verdict
clean — no BLOCKER/SEV1. The load-bearing concern for this layer (sync/blocking
calls inside async) is handled correctly, with real timeouts, memory bounds, and
per-provider isolation. The three SEV2s are defensive hardening on bounded,
single-user-limited surfaces (a thread-leak on a hung upstream, OFX XML entity
hardening, and a yfinance-TOS documentation gap); the rest are polish. Land the
yfinance timeout/semaphore, `defusedxml`, and the TOS note to call it
portfolio-grade.
