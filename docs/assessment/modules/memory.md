# memory — assessed 2026-07-02

Slice: `memory/models.py`, `memory/retrieval.py` (agent conversation/memory + retrieval layer).

## Findings

- [SEV1] memory/retrieval.py:72-113 & memory/models.py:16-70 — no per-user
  scoping on the memory tables. `build_retrieval_context(session, user_id)`
  accepts `user_id` and forwards it to `compute_wealth_position` /
  `compute_income_position`, but the three queries it owns —
  `Decision` (line 72), `Pattern` (line 92), `FinancialSnapshot` (line 110) —
  filter only on `status` / `detected_at` / `computed_at`, never on the user.
  Worse, `Conversation/Message/Decision/Pattern` have **no `user_id` column at
  all** (models.py), so there is nothing to filter on. Single-user v1 is
  correct today, but the moment a 2nd user exists this is a cross-user data
  leak straight into the LLM prompt (decisions + patterns + net worth of every
  user). This is the pre-GA "per-user data isolation" item in CLAUDE.md and
  becomes a **BLOCKER** the instant multi-tenant lands | fix: add
  `user_id: Mapped[str] = mapped_column(String, index=True)` to all four models
  (via Alembic), and `.where(Decision.user_id == user_id)` /
  `.where(Pattern.user_id == user_id)` /
  `.where(FinancialSnapshot.user_id == user_id)` on each query; add a regression
  test asserting user B cannot retrieve user A's decisions/patterns.
- [SEV2] memory/models.py:32 — `Message.conversation_id` is a `ForeignKey`
  with no index. Postgres does not auto-index FK columns, so loading a
  conversation's message history (`WHERE conversation_id = ?`, the natural
  access pattern for chat restore) is a sequential scan that degrades as the
  messages table grows | fix: `mapped_column(ForeignKey("conversations.id"),
  index=True)` and Alembic migration.
- [SEV2] memory/retrieval.py:72,92,110 — the per-request retrieval queries hit
  unindexed sort/filter columns: `decisions(status, decided_at)`,
  `patterns(detected_at)`, `financial_snapshots(computed_at)`. Each is
  `WHERE/ORDER BY ... LIMIT n` → seq scan + in-memory sort. Bounded by `LIMIT`
  (10/5/1) so not an unbounded fetch, but every chat turn pays a scan | fix:
  add `index=True` on `Pattern.detected_at` and `FinancialSnapshot.computed_at`
  (FinancialSnapshot is in vault/ — coordinate), and a composite/partial index
  `decisions(decided_at DESC) WHERE status='active'`.
- [SEV2] memory/retrieval.py:56,62 — `logger.warning("compute_...failed: %s",
  exc)` logs the raw exception from a financial computation. Low probability of
  embedding a decrypted balance, but the computation walks vault figures; a
  driver/validation error could serialize a row value into the message |
  fix (needs-runtime-confirmation): log `exc.__class__.__name__` + a static
  message, or `exc_info=True` to a non-shipping handler, not the interpolated
  `%s` of an arbitrary exception.
- [cleanup] memory/retrieval.py:9 — `import math` is unused (confirmed: only
  occurrence in the file, never referenced). ruff `F401` | fix: delete the line.
- [cleanup] memory/retrieval.py:38-43 — `_WealthPositionContract` and
  `_IncomePositionContract` are empty classes, defined but never referenced
  (dead code masquerading as documentation) | fix: delete both; keep the intent
  in the module docstring or a comment if needed.

## Rubric coverage
| Category | Status |
|---|---|
| 1 Resource lifecycle | ok — session is injected, not owned here; caller closes. No client construction. |
| 2 Concurrency & scale | 3 findings (SEV2 unindexed access patterns + FK) — all queries `LIMIT`-bounded, no N+1, no unbounded fetchall |
| 3 Security & compliance | 1 SEV1 (no per-user isolation / no user_id column) + 1 SEV2 (exception logging); SQL fully parameterized via ORM; sensitive cols encrypted at rest |
| 4 Domain correctness | ok — `_round100` rounds up (ROUND_CEILING) per THREAT_MODEL §4 "never understate"; contract bridging matches CONTRACTS.md §1 shapes; profile block uses `sort_keys` for deterministic cache prefix |
| 5 LLM SDK | n/a — builds the cache-prefix block (deterministic, cache-friendly) but issues no Anthropic call here |
| 6 Cleanliness & typing | 2 cleanup (unused `import math`, 2 dead empty classes); all signatures typed |
| 7 Error handling / API | n/a — not a router/handler module |
| 8 Config & paths | n/a — no paths, no config in this slice |

## Module verdict
NEEDS-WORK — correct and clean for single-user v1, but the memory tables carry
no `user_id` and no query filters by user, so it is a cross-user leak (BLOCKER)
the moment a second user exists; unindexed access patterns and two trivial
dead-code items round it out.
