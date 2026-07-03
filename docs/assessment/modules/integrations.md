# integrations — re-assessed 2026-07-02 (post-remediation)

Branch: `hardening/phase-7-finish-line`. Each original 2026-07-02 finding re-verified
against current code. Prior assessment: NEEDS-WORK.

| # | Sev | Finding | Status | Evidence |
|---|-----|---------|--------|----------|
| 1 | SEV1 | `fetch_price` blocking (requests/yfinance) on event loop, called from async holdings routes | **FIXED** | `integrations/market_data.py:26-38` `fetch_price_async()` wraps sync `fetch_price` in `asyncio.to_thread` + `asyncio.wait_for(timeout=15.0)`. Call sites now use it: `routers/holdings.py:92` (batch loop) and `:115` (single), import at `holdings.py:18`. |
| 2 | SEV1 | yfinance `fast_info` has no timeout | **FIXED** | Bounded by the `asyncio.wait_for` deadline `market_data.py:35`; `TimeoutError` caught/logged `:36-38`. yfinance still has no native timeout (`_fetch_yfinance` `:58-67`) — the outer deadline is the intended bound, matching the expected fix. |
| 3 | SEV2 | csv_import unbounded rows in memory + sync parse on loop; no upload cap | **FIXED** | `MAX_ROWS = 50_000` `csv_import.py:15` raises `ValueError` in `parse_csv` `:98-99` and `parse_ofx` `:136-137`. Parse offloaded via `asyncio.to_thread(parse_ofx/parse_csv, content)` `routers/imports.py:41,44`. Upload cap `MAX_UPLOAD_BYTES = 10 MB` `imports.py:20` enforced on declared size `:31-32` and on actual bytes after read `:34-35` (both → 413). |
| 4 | SEV2 | OFX/QFX XML entity-expansion (defusedxml) | **DEFERRED (Road B)** | `parse_ofx` still uses `ofxtools.Parser.OFXTree` `csv_import.py:113,117-124`; no `defusedxml`. Deferral holds: authenticated single-owner uploader (`_user: CurrentUser` `imports.py:29`) and 10 MB size cap bound the expansion input. Confirmed as accepted deferral. |
| 5 | cleanup | no pooled `requests.Session` | **FIXED** | Module-level `_session = requests.Session()` `market_data.py:23`, used by Alpha Vantage fallback `:74`. |

## Notes on other original cleanups (not in the 5-item re-verify scope)
- Broad `except Exception` in `market_data.py:65,86` and `property_data.py:66` — still present (OPEN, low sev, intentional fail-soft returning `None`).
- Typing gaps `ParsedRow.raw: dict` `csv_import.py:23` and `mappings: list` `:152` — still untyped (OPEN, cosmetic).
- Out-of-scope residual: `property_data.fetch_property_estimate` `:36-68` is still synchronous with a bare `requests.get` (no pooled session); monthly-quota-limited (50/mo) and, per prior notes, consumed via `to_thread` at its router call site, so it does not reintroduce finding 1.

## Module verdict
**PASS (post-remediation).** All SEV1/SEV2 code defects in the re-verify scope (findings
1, 2, 3) are FIXED with in-code evidence, the pooled-session cleanup (5) is FIXED, and the
sole DEFERRED item (4) is a documented, bounded Road-B deferral consistent with the
single-user threat model. The module clears the concurrency/scale blockers that drove the
prior NEEDS-WORK verdict. Remaining items are low-severity cleanups only.
