# integrations — assessed 2026-07-02

## Findings
- [SEV1] integrations/market_data.py:56 & :42 — `fetch_price()` uses blocking
  `requests.get` (Alpha Vantage) and blocking `yf.Ticker().fast_info` (yfinance),
  and it is called **directly on the event loop** from `async def refresh_all_prices`
  (routers/holdings.py:95, in a per-ticker loop) and `async def refresh_single_price`
  (routers/holdings.py:118). Each call stalls the single-threaded loop for the full
  network round-trip; the batch route serializes N blocking calls, freezing every
  concurrent request on that worker (axis B). Note property_data is consumed
  correctly via `asyncio.to_thread` (routers/vault.py:512) — market_data is not |
  fix: wrap both call sites in `await asyncio.to_thread(fetch_price, ticker)`, or
  convert market_data to an `httpx.AsyncClient` module-level singleton and make
  `fetch_price` async. yfinance stays sync, so `to_thread` is the pragmatic fix.
- [SEV1] integrations/market_data.py:42 — `yf.Ticker(ticker).fast_info` performs an
  HTTP fetch with **no timeout** (yfinance exposes none here); a slow/hung upstream
  blocks indefinitely (axis E — a call with no timeout is an outage waiting to
  happen), compounded by running on the loop | fix: run under `asyncio.to_thread`
  with an outer `asyncio.wait_for(..., timeout=10)` deadline, or replace fast_info
  with a direct `requests.get` to the quote endpoint using a `Session` + `timeout`.
- [SEV2] integrations/csv_import.py:71-103 (parse_csv) & :112-142 (parse_ofx) —
  untrusted uploaded file is fully read (routers/imports.py:26 `await file.read()`,
  no size cap anywhere), then `content.decode(...)` and an unbounded `rows` list are
  built entirely in memory; the parse also runs synchronously on the event loop.
  A large/crafted upload exhausts memory and stalls the loop (axis E / untrusted
  parsing) | fix: enforce a max upload size (e.g. reject > 10 MB via a
  Content-Length / streamed byte-count guard in imports.py) AND cap rows in
  parse_csv (e.g. `if len(rows) >= MAX_ROWS: raise ValueError`); run the parse via
  `asyncio.to_thread(parse_csv, content)`.
- [SEV2] integrations/csv_import.py:118 — `parser.parse(io.BytesIO(content))` feeds
  an untrusted OFX/QFX (XML) file into ofxtools' ElementTree-based parser; XML entity
  expansion ("billion laughs") is a DoS surface for untrusted XML
  (needs-runtime-confirmation on ofxtools' entity handling) | fix: confirm ofxtools
  disables entity resolution, or pre-parse with `defusedxml`; at minimum apply the
  same upload size cap.
- [cleanup] integrations/market_data.py:47,68 & integrations/property_data.py:66 —
  bare `except Exception` swallows all errors (incl. programming errors) and returns
  None silently | fix: narrow to `requests.RequestException`, `ValueError`,
  `InvalidOperation`.
- [cleanup] integrations/market_data.py:56 & property_data.py:43 — `requests.get`
  per call constructs a fresh connection each time; no pooled client
  (rubric 1: external clients should be module-level singletons) | fix: use a
  module-level `requests.Session()` (or the httpx.AsyncClient singleton from the
  SEV1 fix) so TCP/TLS connections are reused.
- [cleanup] integrations/csv_import.py:20 — `raw: dict` untyped param on ParsedRow |
  fix: `raw: dict[str, str]`.
- [cleanup] integrations/csv_import.py:145 — `_apply_mappings_raw(..., mappings: list)`
  untyped element type | fix: `mappings: list[CategoryMapping]` (or a small Protocol
  exposing `.pattern` / `.category`).

## Rubric coverage
| Category | Status |
|---|---|
| 1 Resource lifecycle | 1 finding (no pooled HTTP client; temp/handle paths ok) |
| 2 Concurrency & scale | 2 SEV1 (blocking calls on event loop) + 2 SEV2 (unbounded parse) |
| 3 Security & compliance | ok — keys from typed settings (config.py:43-44), never logged; explicit no-log-url comment; parameterized ORM inserts at caller |
| 4 Domain correctness | ok — AVM disclaimer constant defined; enforcement correctly delegated to router (documented) |
| 5 LLM SDK | n/a (no LLM in this module) |
| 6 Cleanliness & typing | 3 cleanup (broad except, typing gaps) |
| 7 Error handling / API | n/a (library module; HTTP status mapping lives in routers) |
| 8 Config & paths | ok — both keys in .env.example, typed `str \| None`, no filesystem paths |

## Module verdict
NEEDS-WORK — no cross-tenant/secret leak, but market_data does blocking HTTP
(incl. one with no timeout) on the event loop, and CSV/OFX parsing of untrusted
uploads is unbounded in memory; fix the async offloading, add a timeout, and cap
upload size before scale.
