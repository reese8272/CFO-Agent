# WEB_STANDARDS.md — Evergreen Technical + Style Reference

Calibrated for this project: single-user finance app, $0 infra budget, LLM-heavy,
Oracle Cloud Free ARM VM, Cloudflare Tunnel, FastAPI + Postgres + Redis + vanilla HTML.

Each item is marked:
- **✦ Non-negotiable** — skip this and production breaks, users are at risk, or costs spiral
- **◇ Nice-to-have** — real improvement, but not a blocker at current scale

---

## Part 1 — Technical Standards

---

### 1. Performance

**Targets (Core Web Vitals — Google search ranking since 2024):**

| Metric | Target | What it measures |
|---|---|---|
| LCP (Largest Contentful Paint) | < 2.5 s | How fast the main content loads |
| CLS (Cumulative Layout Shift) | < 0.1 | Visual stability — no jumping elements |
| INP (Interaction to Next Paint) | < 200 ms | Responsiveness to clicks/taps |

**Checklist:**

- ✦ **HTTP/2** — any modern reverse proxy (Nginx, Cloudflare) gives this for free; enables request multiplexing
- ✦ **Brotli/gzip compression** on all text assets (HTML, CSS, JS, JSON responses) — Cloudflare applies Brotli automatically
- ✦ **`Cache-Control: immutable`** on fingerprinted static assets (fonts, versioned JS/CSS bundles)
- ✦ **`Cache-Control: no-store`** on any response that contains user-specific data
- ✦ **Lazy-load below-the-fold content** — images, deferred JS, off-screen sections
- ◇ **WebP/AVIF images** — ~50% smaller than JPEG/PNG at equivalent quality; AVIF is the 2025 gold standard
- ◇ **CDN edge caching** for public static assets — Cloudflare free tier covers this at current scale

---

### 2. Database

- ✦ **Connection pooling** — never open a raw connection per request. SQLAlchemy `pool_size=10, max_overflow=5` is the standard starting point. Postgres default max is 100 connections; account for every worker + background job
- ✦ **Index every foreign key** — Postgres does not auto-index FK columns. An un-indexed FK on a hot JOIN is a silent full-table scan
- ✦ **Index every column that appears in a WHERE clause on a hot path** — `EXPLAIN ANALYZE` before shipping any new query pattern
- ✦ **Avoid N+1 queries** — if you're fetching a list and then querying each item individually, use `joinedload` / `selectinload` or a batch query. N+1 is the most common production performance incident
- ✦ **Parameterized queries always** — no f-string interpolation into SQL. SQLAlchemy ORM enforces this automatically; raw `text()` calls must use `:param` binding
- ✦ **Migrations are forward-only and tested before deploy** — never run a destructive migration without a rollback plan; test on a copy of prod schema before applying
- ✦ **Automated daily backups with one offsite copy** — `pg_dump` + encrypted upload to object storage. Test restore at least quarterly (an untested backup is not a backup)
- ◇ Partial indexes, covering indexes — real gains on large tables; irrelevant at v1 scale
- ◇ Read replicas — only needed when read load justifies it

---

### 3. Caching

**Layer model (outer → inner):**

```
Browser cache → CDN edge → Application cache (Redis) → DB query cache → DB
```

**Redis patterns:**

| Pattern | When to use |
|---|---|
| **Cache-aside** | Default. Read from Redis; on miss, query DB, write to Redis with TTL |
| **Write-through** | When stale reads are dangerous (e.g. auth tokens, vault mutation results) |
| **TTL on everything** | No exceptions. Unbounded cache growth is a production incident |

**HTTP cache headers:**

| Header | Value | Use |
|---|---|---|
| `Cache-Control: no-store` | — | Any response with PII or session data |
| `Cache-Control: max-age=31536000, immutable` | — | Fingerprinted static assets |
| `Cache-Control: max-age=300` | — | Public, non-personalized API responses |
| `ETag` | hash of response body | Allows 304 Not Modified for unchanged data |

**LLM response caching (this project):**

- ✦ **Anthropic prompt caching** on all vault snapshot / profile blocks — mandatory; reduces input token cost ~90% on cache hits. Already implemented; verify cache_control headers are present on every profile block
- ◇ **Redis exact-match cache** on deterministic prompts (same vault hash + same question) — real cost saving; implement when LLM spend becomes noticeable
- ✦ **Log token usage after every LLM call** — `tokens_in`, `tokens_out`, `cache_read_tokens`, `latency_ms`. Already in the codebase; keep it

**Security note:** Never cache authenticated, user-specific responses at the CDN layer without per-user cache key scoping. Cloudflare's default behavior bypasses caching for cookies/auth headers — verify this assumption before adding any CDN cache rules.

---

### 4. API & Backend

- ✦ **Rate limiting on every public endpoint** — token bucket or sliding window; 429 with `Retry-After` header. Especially critical on `/chat` (each call hits the LLM). Current gap: `/chat` has no rate limit. Prioritize before any second user
- ✦ **Correct HTTP status codes** (a 200 on an error is never acceptable):

| Situation | Code |
|---|---|
| Bad input format | 400 |
| Missing / invalid auth token | 401 |
| Valid token, insufficient permissions | 403 |
| Resource not found | 404 |
| Validation failure (Pydantic) | 422 |
| External service failure | 502 |
| Internal error | 500 |

- ✦ **Timeouts on every external call** — Anthropic, RentCast, yfinance. No open-ended `await`. `LLM_TIMEOUT_SECONDS` env var already covers the Anthropic client; verify it's wired to all nodes
- ✦ **Input validation at the system boundary** — Pydantic on every endpoint body and path/query param. Already enforced; never validate inside business logic instead of at the router
- ✦ **Cursor-based pagination** on any list endpoint that can grow unbounded — offset pagination (`OFFSET 1000 LIMIT 20`) degrades linearly with table size. For v1 this is a known gap; add before any data grows large
- ◇ Circuit breakers on external calls — meaningful when you have multiple downstream services; overkill at current scale

---

### 5. Frontend / UI

- ✦ **Loading, error, and empty states on every data-fetching component** — the most commonly skipped requirement. A spinner is not enough; an error state must let the user recover (retry button or clear message)
- ✦ **WCAG AA contrast minimums**:
  - Body text: 4.5:1 contrast ratio against background
  - Large text (18px+ or 14px+ bold) and UI components: 3:1
  - Use a contrast checker before shipping any new color combination
- ✦ **All interactive elements keyboard-reachable** with a visible focus indicator — `outline: none` without a replacement is an accessibility regression
- ✦ **Semantic HTML** — `<button>` for actions, `<a>` for navigation, `<input>` for inputs. Never `<div onclick>`. Screen readers and keyboard users depend on this
- ✦ **`<form>` with `action` + `method`** even when JS handles submission — graceful degradation baseline
- ◇ Skip-nav links for keyboard users on pages with long navigation
- ◇ `aria-live` regions for dynamically updated content (chat responses, loading indicators)
- ◇ Full screen-reader audit — meaningful before a second user; not required at single-user

---

### 6. Deployment & Executability

Every production service must have all of the following:

- ✦ **`GET /health`** returning `{"status": "ok", ...service checks...}` — already implemented. Automated infrastructure (Docker healthcheck, Cloudflare health check) depends on this
- ✦ **Structured logging** — JSON lines format, every log line machine-parseable. Python `logging` module with a JSON formatter. `print()` is banned in production code. Currently using `logging`; keep it
- ✦ **Secrets via environment variables** — never in code, image layers, or git. `.env` files never committed. Already enforced by CI audit
- ✦ **Graceful shutdown** — drain in-flight requests before the process exits. FastAPI + uvicorn handle `SIGTERM` gracefully when `--timeout-graceful-shutdown` is set (default 0 in Docker; set to 15-30s)
- ✦ **Container auto-restart** — `restart: unless-stopped` in docker-compose. Already set. Keeps the app up through transient crashes without manual intervention
- ✦ **Alembic migrations run before app boot** — guaranteed by deploy script. Never apply a migration after a new code version is already serving traffic
- ◇ Zero-downtime deploys (blue/green or rolling) — currently the app has a brief restart window on deploy. Acceptable at single-user; fix before multi-user
- ◇ Prometheus metrics endpoint — useful when you have a dashboard to consume it; not worth the overhead at v1

**Monitoring minimum:**
- ✦ External uptime check hitting `/health` every 5 minutes with an alert on failure. Free options: UptimeRobot (free tier), Healthchecks.io dead-man's-switch. Already wired via optional `HEALTHCHECK_PING_URL`
- ◇ Error tracking (Sentry free tier) — meaningful when you have users you can't personally observe

---

### 7. Cost Optimization

**Free-tier infrastructure (current):**

| Layer | Tool | Cost |
|---|---|---|
| VM | Oracle Cloud Free (4 ARM vCPU, 24 GB RAM) | $0 |
| Ingress / TLS | Cloudflare Tunnel + free plan | $0 |
| DB | Postgres in Docker on the same VM | $0 |
| Cache | Redis in Docker on the same VM | $0 |
| CI/CD | GitHub Actions (2000 min/mo free) | $0 |
| Container registry | GHCR (free for public repos) | $0 |

**LLM cost controls (✦ all non-negotiable for any LLM app):**

- ✦ **Prompt caching** on all repeated context blocks — already implemented; reduces input cost ~90% on cache hits
- ✦ **`max_tokens` hard limit on every API call** — prevents runaway generation costs. `LLM_TIMEOUT_SECONDS` handles wall-clock; `max_tokens` handles token spend
- ✦ **Log token usage after every call** — `tokens_in`, `tokens_out`, `cache_read_tokens`. Already in codebase. Review weekly during active use
- ✦ **Billing alert thresholds** — set alerts at $5, $20, $50 in the Anthropic console. The most common surprise is a loop calling the LLM on every keystroke or page load
- ◇ **Redis exact-match cache on deterministic prompts** — implement when monthly LLM spend exceeds $10. Cache key = `hash(vault_hash + normalized_message)`
- ◇ **Batch API** for non-real-time LLM calls (digest generation, weekly analysis) — ~50% cost reduction vs. real-time API; Anthropic Batch API supports async jobs

**DB connection limits:**
- Postgres default: 100 max connections. With `pool_size=10` and one app instance you're at 10. When adding workers or background jobs, sum all pool sizes and stay under 80 (leave headroom for migrations and admin queries)

---

## Part 2 — Style & Color Reference

---

### Concept-to-Palette Mental Model

These are archetypes, not prescriptions. The psychological basis is why the association is sticky and why deviating from it costs trust.

---

#### Finance / Wealth

**Palette archetype:** Deep navy or forest green + cream/off-white + gold accent

**Psychological basis:** Navy is inherited from investment banking print design — it signals institutional authority and long-term stability. Forest green activates the literal money-growth association while feeling grounded rather than flashy. Gold suggests aspiration without neon vulgarity. Cream/off-white reads as premium vs. pure white (which reads as utilitarian).

**Layout signals:** Data-dense, high information hierarchy, conservative spacing. Density signals competence — a tool that takes you seriously treats you as someone who can handle numbers.

**Avoid:** Bright red (loss/danger connotation in financial contexts), neon or gradient-heavy palettes (signals consumer/gaming, not wealth management).

*This project uses forest green (#7A9B83) + dark surface (#252B28) + sage accents — correct archetype.*

---

#### Tech / SaaS

**Palette archetype:** Dark-mode default with single electric accent (electric blue #0EA5E9, violet #8B5CF6, or lime #84CC16). Neutral gray scale for surfaces.

**Psychological basis:** Dark backgrounds reduce eye strain for power users who live in the tool all day. A single accent creates clear visual hierarchy without competing colors. The accent does all the CTA work; surfaces stay neutral.

**Layout signals:** Generous white space (in light mode) or dark surface hierarchy (in dark mode), cards as containers, monospace font for code/data. Component-first design.

**Avoid:** Multi-accent palettes (signals design-by-committee), pure black backgrounds (hard edges; use #111 or #1A1A1A instead).

---

#### Healthcare / Wellness

**Palette archetype:** Clinical white or light gray + teal (#0D9488) or soft blue (#60A5FA) + warm neutral accents

**Psychological basis:** Teal splits the difference between medical authority (blue) and vitality/wellness (green). Rounded corners and generous spacing signal approachability and care. The palette must feel clean without feeling cold or pharmaceutical.

**Layout signals:** Card-heavy, lots of whitespace, icons over dense data. Legibility over density.

**Avoid:** Red (triggers medical emergency associations), dense data tables (feels clinical/cold for wellness; acceptable for clinical/medical software).

---

#### Enterprise / B2B

**Palette archetype:** Muted corporate blues and grays (#1E3A5F, #64748B), high-contrast accent (blue #2563EB or orange #EA580C), white backgrounds

**Psychological basis:** Enterprises buy with committees. The palette signals "nothing surprising here" — safe, trustworthy, won't embarrass anyone in a board deck. Brand colors are often mandated by the buyer organization.

**Layout signals:** Tables over cards, left-nav sidebar, information density. Accessibility compliance is often contractual (WCAG AA minimum, often AA+). Headers and footers are load-bearing.

**Avoid:** Dark mode as default (enterprise procurement often requires light mode as the baseline), expressive/personality-forward typography.

---

#### Consumer / Social

**Palette archetype:** Saturated, expressive primary palette with brand personality as the leading design decision. Color *is* the brand.

**Psychological basis:** Consumer products compete for emotional resonance. Color signals personality before a user reads a word. The palette must be distinctive enough to be recognizable at thumbnail size.

**Layout signals:** Generous white space between high-color elements. Typography as visual art (custom wordmarks, display fonts). Mobile-first, thumb-reachable CTAs.

**Avoid:** Muted palettes (signals enterprise, not consumer), dense data layouts.

---

#### Minimal / Editorial

**Palette archetype:** Near-monochrome — white, off-white, near-black + single high-contrast accent (black + red, cream + forest green, white + gold)

**Psychological basis:** The constraint signals confidence. If you only use one accent color, it had better mean something. Common in premium brands, journalism, and portfolio work where the content is the hero.

**Layout signals:** Asymmetric layouts, large display typography as a visual structural element, white space as composition. Grid-breaking is intentional, not accidental.

**Avoid:** Multiple accent colors (defeats the constraint), stock-photo-heavy layouts.

---

### Typography Standards

| Property | Standard | Notes |
|---|---|---|
| Base font size | 16px (14px min) | 16px is WCAG recommended; 14px acceptable for utility/data-dense UIs |
| Body line-height | 1.5 | 1.4 minimum; 1.6 for long-form reading |
| Heading line-height | 1.1–1.25 | Tighter than body; headings are scanned, not read |
| Characters per line | 60–75 ch | Beyond 75ch, eyes lose their place. `max-width: 65ch` on prose containers |
| Heading scale | 1.25× or 1.333× modular ratio | 1.25× (major third) for data-dense UIs; 1.333× (perfect fourth) for editorial |
| Font weight contrast | 400 body / 600–700 headings | Weight contrast is more reliable than size alone for hierarchy at small scales |
| Font families | Max 2–3 | One for body, one for headings (optional), monospace for code/data |
| System font stack | Acceptable for utility apps | `-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif` — zero load cost |

**Font loading:** If using a web font, `font-display: swap` to prevent invisible text during load. Preconnect to the font CDN (`<link rel="preconnect">`). Subset to only the weights actually used.

---

### Spacing Grid

**8px base grid** — universal across design systems (Material, Tailwind, Bootstrap all derive from it).

Standard steps:

| Name | px | rem | Use |
|---|---|---|---|
| xs | 4 | 0.25 | Icon padding, tight inline gaps |
| sm | 8 | 0.5 | Gap between related inline elements |
| md | 16 | 1 | Default field padding, card inner padding |
| lg | 24 | 1.5 | Section spacing within a card |
| xl | 32 | 2 | Between major sections on a page |
| 2xl | 48 | 3 | Page-level top/bottom padding |
| 3xl | 64 | 4 | Hero sections, large layout gaps |

**Rule:** Consistent application matters more than the specific scale. Pick a grid and never deviate from it — visual rhythm breaks whenever you use ad-hoc values like 13px or 22px.

---

### Quick Reference: Contrast Ratios (WCAG AA)

| Text type | Minimum ratio | Tools |
|---|---|---|
| Normal body text (< 18px regular, < 14px bold) | 4.5:1 | coolors.co/contrast-checker |
| Large text (18px+ regular or 14px+ bold) | 3:1 | |
| UI components (buttons, inputs, focus rings) | 3:1 | |
| Decorative / logo | No requirement | |

**Fail-safe check:** If you can read a dark label on a sage/muted background, verify the ratio. Muted greens and blues are the most common contrast failures in design-forward UIs.

---

*Last updated: 2026-05-28. Revisit the performance targets and cost section annually — Core Web Vitals thresholds and LLM pricing change frequently.*
