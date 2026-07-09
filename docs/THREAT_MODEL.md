# Threat Model

**Scope**: Personal-cfo, v1, single-user. **If a second user is ever invited, redo this file before the invite.**
**Last updated**: 2026-05-23

> **Disclaimer**: This tool is for financial education and personal organization. It is not a licensed financial advisor. For tax strategy, real estate transactions, and investment decisions, consult a licensed professional.

---

## Threats (in order of likelihood)

### 1. Device theft with active session
- **Risk**: Attacker with physical device gets the running app + an unexpired JWT.
- **Mitigations**:
  - Short JWT TTL (`JWT_EXPIRY_MINUTES`, default 60)
  - Full-disk encryption on host VM and dev laptop
  - Fernet encryption on sensitive columns — DB dump alone is useless without `VAULT_ENCRYPTION_KEY`

### 2. Accidental `.env` git push
- **Risk**: Secrets (Anthropic key, Postgres password, Fernet key, JWT secret, Plaid creds) committed and pushed publicly.
- **Mitigations**:
  - `.gitignore` blocks `.env`, `.env.*` (except `.env.example`)
  - Pre-commit hook scans staged content for known secret patterns
  - `VAULT_ENCRYPTION_KEY` never embedded in code or fixtures
  - Rotation runbook required before key change

### 3. Backup file leak
- **Risk**: Off-host backup of Postgres dump exposes encrypted blobs; if encryption key is also leaked, exposes everything.
- **Mitigations**:
  - Backups encrypted with a separate key from `VAULT_ENCRYPTION_KEY`
  - Backup storage off the application host
  - Backup key access logged

### 4. Anthropic log retention
- **Risk**: Prompts sent to Anthropic could surface in their logs if accessed.
- **Mitigations**:
  - Anthropic prompts redact account numbers and precise dollar balances unless arithmetic precision is required — pass rounded aggregates by default
  - Last-4s only (never full account numbers) when identifiers are needed
  - No SSN, no full address, no DOB in prompts

### 5. Plaid breach (phase 2)
- **Risk**: Plaid is compromised; access tokens or account metadata exposed.
- **Mitigations** (in our control):
  - Plaid access tokens encrypted in `accounts.plaid_access_token_encrypted`;
    account identifiers encrypted in `accounts.plaid_account_id_encrypted` (2026-07-09)
  - Rotate on `ITEM_LOGIN_REQUIRED` webhook; user re-links via standard Plaid Link flow
  - Single bank link minimization — link only accounts the agent needs

---

## Out of Scope

- Nation-state adversary
- Insider threat at Anthropic
- Supply-chain compromise (Python packages, Docker images)
- Browser zero-days
- Multi-user data isolation (single-user v1)

---

## Posture Statement

The above mitigations are calibrated to a personal threat model. Encrypt at rest, fail closed on missing keys, redact at API boundaries, audit every mutation, restrict prompt exfiltration to aggregates. No GDPR / CCPA / breach-notification scope while single-user.

---

## Triggers to Revisit

Redo this file when any of the following occurs:

- A second user (anyone other than the owner) is given access
- Plaid integration ships (Issue 13)
- Any new third-party API integration is added
- The hosting host changes (e.g., off Oracle Cloud)
- An incident — actual or suspected — occurs
- Annually, regardless
