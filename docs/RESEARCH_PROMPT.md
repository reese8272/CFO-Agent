# Research Prompt: Financial Freedom Pathways for an Early-Career Multi-Income Earner

> Drop this prompt into Claude (with research / web), GPT (deep research), Perplexity Pro, or any AI researcher with web access. Save the output to `docs/RESEARCH_NOTES.md` (gitignored if you want it private, or committed to the repo as source material). Cleanest principles port into `docs/WEALTH_PRINCIPLES.md`; year-versioned tax constants port into `agent/principles.py`; arena-specific libraries into `agent/principles_real_estate.py`, `agent/principles_saas.py`, `agent/principles_investing.py`.

---

## Your Role
You are a senior financial researcher synthesizing the highest-signal advice, frameworks, and quantitative constants for the principle library of a personal CFO + career strategist AI agent. Your output will be cited verbatim by an LLM-based coach in chat responses, so **accuracy, sourcing, year-stamping, and a one-sentence-citable format matter more than breadth.** No generic personal-finance listicles.

## Subject Profile (the human the agent coaches)
- Early-career US-based W-2 software engineer (Cognizant) + 1099 gig driver (DoorDash, ~3 nights/week) + cash coaching income
- Goal: financial freedom, target seven-figure net worth on a 10–15 year horizon
- Open paths of interest: index-fund investing, real estate, SaaS / indie business
- Already familiar with basic budgeting; building deeper expertise from here
- Wants a coach voice — encouraging, real, not sugarcoated, names the long game (think Naval Ravikant + Codie Sanchez + Patrick McKenzie + Bogleheads, not Suze Orman)

## Product Context (so your output fits the agent's structures)
The agent reasons across two parallel tracks on every chat turn:
- **Allocation track** (6 steps): emergency fund → eliminate high-APR debt → max tax-advantaged → market exposure → real estate leverage → ownership/business
- **Income track** (5 steps): net hourly truth → cut the bottom → career velocity → 1099 deduction discipline → negotiation practice

Each recommendation cites a **named principle** (one sentence the coach speaks aloud) backed by a longer paragraph for when the user asks "explain that more." Year-versioned tax constants live separately and are stamped with the tax year ("for 2026..."). The agent's mental scaffold is **assets-over-liabilities** (Rich Dad / Naval / Codie Sanchez lens) and **net worth as the headline metric** — every recommendation should be stampable against "does this move you toward your 10-year vision?"

## What I Need From You

For each of the **11 domains** below, produce:

1. **5–10 named principles**, each formatted as:
   - **Name** — 3–6 words, memorable, action-oriented
   - **One-sentence statement** — exactly what the coach says when citing it
   - **Three-sentence explanation** — the why, the math when relevant, the common failure mode
   - **When to apply** + **when NOT to apply**
   - **Source(s)** — primary research, book + chapter, IRS pub, or a well-regarded author/blogger; no generic listicles

2. **Numeric constants for tax year 2026** where applicable, with source (IRS pub number, official table, or equivalent)

3. **Further reading** — 2–3 top resources (books / blogs / podcasts) with one sentence each on why they belong on the list

## The 11 Domains

1. **Foundational personal finance principles** — debt avalanche vs snowball, time-in-market, tax arbitrage by bucket, lifestyle creep, employer match capture, savings rate vs return rate at different career stages, the gap between knowing and doing

2. **2026 US tax constants and rules** affecting W-2 + 1099 earners — Roth IRA limit, Traditional IRA limit, 401(k) employee + employer limits, Solo 401(k) combined limit, SEP-IRA limit, HSA limit, FSA limits, federal brackets, capital-gains brackets, SE tax rate, standard mileage rate, standard deduction, quarterly estimated-tax deadlines, S-Corp election rule-of-thumb threshold

3. **Asset vs liability mental models** — Rich Dad framing, Naval Ravikant on specific knowledge + leverage + equity, Codie Sanchez on boring businesses, Morgan Housel on "enough," the difference between an asset that pays you and a status purchase

4. **Real estate from zero** (getting to first property)
   - House hacking (FHA 3.5%, duplex/triplex/fourplex, owner-occupant rules)
   - BRRRR — when it works, when it doesn't in current-rate environments
   - Conventional vs FHA vs VA vs USDA loans
   - First-time buyer programs (federal + commonly-cited state programs)
   - Analytical frameworks: 1% rule, 50% rule, cap rate, cash-on-cash, GRM, DSCR
   - Market analysis (rentometer, population/job-growth leading indicators)
   - REITs vs direct ownership (tax, liquidity, leverage tradeoff)
   - Common mistakes (under-budgeting capex, ignoring property management cost, falling in love with the property)

5. **SaaS / indie business building**
   - Bootstrapping vs VC (when each fits)
   - Pricing models — free trial vs freemium vs reverse trial, anchoring, value-metric selection
   - MRR/ARR mechanics, churn (gross vs net dollar retention), CAC/LTV
   - Distribution-first thinking (Pieter Levels, build-in-public, Justin Welsh on solopreneur leverage)
   - When to leave W-2 (savings runway, MRR threshold, health-insurance considerations)
   - Common mistakes (building before talking to customers, over-engineering, undercharging)
   - Notable micro-SaaS playbooks (MicroConf, Tiny SaaS, Stair-Step method)

6. **Index-fund investing (long-term wealth via market exposure)**
   - Three-fund portfolio (Bogleheads): US total market + international + bonds
   - Target-date funds (when they win, when they lose vs roll-your-own)
   - Brokerage selection (Fidelity vs Vanguard vs Schwab — fees, fractional, tax features)
   - Tax-loss harvesting (how, when, wash-sale rule)
   - Asset allocation by age (rule of 110, lifecycle funds)
   - Rebalancing cadence
   - Common mistakes (market timing, stock picking, chasing recent winners, ignoring expense ratios, exotic ETFs)

7. **Career velocity for software engineers**
   - Comp benchmarks (Levels.fyi, Pave, H1B data)
   - Job-switch cadence — 2–4 year sweet spot, Pew/BLS data on switch deltas
   - Negotiation (Patrick McKenzie "Salary Negotiation," Haseeb Qureshi tech-specific guide, levels.fyi negotiation course)
   - Promotion paths IC vs management (Will Larson, Camille Fournier)
   - FAANG / big-tech comp arbitrage — when it's worth pursuing
   - Specialization vs generalization tradeoff

8. **1099 / gig / coaching income optimization**
   - Solo 401(k) mechanics — employee + employer contributions, Roth Solo 401(k), when SEP-IRA wins instead
   - Deduction discipline — standard mileage vs actual, home office (regular vs simplified), Section 179 / bonus depreciation, education, software, business meals
   - Quarterly estimated tax — Form 1040-ES, safe-harbor rules, penalty avoidance
   - S-Corp election — typical ~$60k+ net SE income threshold, reasonable-salary requirement, SE-tax savings on distributions
   - Minimum bookkeeping (separate business checking, accounting software, receipts)
   - Coaching-specific: rate setting, packaging, when to raise rates

9. **Financial freedom / FIRE math**
   - 4% rule (Trinity Study; updates by Wade Pfau, Big ERN)
   - Variants: LeanFIRE, FatFIRE, Coast FIRE, BaristaFIRE — definitions and target multiples
   - Safe withdrawal rate sensitivity (sequence-of-returns risk in early retirement years)
   - Geographic arbitrage (HCOL → MCOL → LCOL, overseas options)
   - Passive income required = annual expenses ÷ 0.04
   - Healthcare bridge from FIRE to Medicare (ACA subsidies, healthshares)

10. **Behavioral finance & habits**
    - Automate everything (pay-yourself-first, auto-rebalancing)
    - Lifestyle creep mechanics (raise → savings-rate auto-bump)
    - Decision fatigue → reduce financial decisions per month
    - Loss aversion in downturns (the cost of selling at the bottom)
    - Identity-based habits (James Clear: "I'm the kind of person who invests every paycheck")
    - What to track vs what to ignore — net worth monthly, savings rate weekly, do NOT obsess over daily expenses

11. **Path-to-$1M frameworks calibrated to an early-career multi-income earner**
    - "Aggressive saver" path — max 401k + Roth + brokerage, 50%+ savings rate, year-by-year net-worth milestones
    - "Real estate leveraged" path — house hack year 1, rental year 3, BRRRR loop
    - "Business builder" path — side SaaS or service business, replace W-2 by year N
    - "Career climber" path — FAANG-level comp arbitrage, index funds do the rest
    - "Mixed" path (most common in practice)
    - Realistic year-by-year net-worth milestones for each starting from ~$0 and ~$50k baselines
    - When to switch paths (signal-based, not vibes-based)
    - Common failure modes (lifestyle creep, golden handcuffs, business burnout, cap-rate compression on rentals)

## Output Format

Return a single Markdown document, top-level sections for each of the 11 domains. Within each:

```
### Principles
(the 5–10 named principles, formatted per the spec above)

### Constants / Numbers (year-stamped)
(if applicable)

### Further Reading
(2–3 items max, each with one sentence on why)
```

At the end of the document, add three closing sections:

- **Top 10 highest-leverage principles overall** for someone fitting the Subject Profile, ranked with a one-sentence justification each
- **Top 5 books to read in order** for someone starting from this profile
- **Red flags / advice to ignore** — whole life insurance as investment, infinite banking concept, MLMs disguised as opportunity, day trading, options-income strategies, get-rich-quick courses, anything "passive income course" priced over $500

## Hard Requirements

- **Cite sources for every quantitative claim** — IRS pub, primary research, book + chapter, or named author with link
- **Year-stamp every tax / contribution number** explicitly ("for tax year 2026...")
- **Refuse state-specific tax/legal advice** — flag where state context matters and route to CPA/CFP
- **Pass the "top-tier advisor language" test** — no fluff, no padding, no "5 ways to..." listicles
- **Distinguish hype from durable wisdom** — flag strategies that are current-conditions-dependent (e.g., BRRRR in a high-rate environment)
- **No investment advice on individual securities** — index funds and asset classes only
- **Where two reputable experts disagree, name both views and the reasoning** — don't pretend consensus exists where it doesn't
