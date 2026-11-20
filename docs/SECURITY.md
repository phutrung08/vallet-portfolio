# Security Model

This document defines Vallet's security architecture, threat model, and implemented controls across the backend, frontend PWA, HTTP edge, and CI supply chain.

## Protected Assets

| Asset | Exposure Impact | Primary Controls |
|---|---|---|
| Trip records (member names, expenses, notes, places, activity history) | Personal data of trip participants who never registered accounts | Active-member authorization (`TripMember`), random UUIDs, row locking, offline cache eviction on revocation |
| Beneficiary bank accounts for VietQR settlement | Financial spoofing if altered; sensitive personal account numbers | Self-only `/members/me/bank-account` endpoint, AES-256-GCM encryption at rest with row-bound AAD, `Cache-Control: no-store`, event audit trail |
| Trip share tokens & device session tokens | Bearer capability to read and mutate trip data | 256-bit HMAC / random tokens, SHA-256 hashed DB storage, URL hash-fragment invites (`/join#<token>`), `HttpOnly` `__Host-vl_device` cookies |

Vallet never stores bank credentials, card numbers, or holds user funds; VietQR codes prefill a transfer in the member's own banking app with a masked last-4 account confirmation display.

## Threats & Controls

### 1. Share Link Exposure Outside the Group

- **HMAC derivation (`app/core/security.py`, `app/services/trips.py`):** Invite tokens are derived via `HMAC-SHA256(VALLET_SHARE_LINK_KEY, "share:v1:{trip_id}:{share_token_version}")` and encoded as unpadded base64url (256 bits). Existing members can view the current invite without persisting plaintext tokens, while `VALLET_SHARE_LINK_KEY` must be distinct from development defaults and at least 32 bytes outside `development`.
- **Hashed database lookup (`app/api/join.py`):** PostgreSQL stores only `SHA-256(token)` in `share_token_hash`.
- **Fragment transport & no-store caching:** Invite links pass the token in the URL hash fragment (`/join#<token>`), which browsers omit from HTTP request lines and `Referer` headers. The frontend exchanges the token strictly via `POST /api/join/preview` and `POST /api/join`, and both `/share-link` and `/join/preview` return `Cache-Control: no-store`.
- **Instant invalidation:** Rotating a trip's share link increments `share_token_version` (`POST /trips/{trip_id}/share-link/rotate`), immediately returning `404` for old tokens while keeping existing members signed in. Locking a trip blocks all writes, joins, and link rotations until unlocked.

### 2. Broken Object-Level Authorization (IDOR) & Privilege Races

- **Centralized membership dependency (`app/api/deps.py`):** Every trip-scoped route resolves `TripMember` (`require_member`), verifying an active device session attached to an active (non-removed) member of `trip_id`. Missing sessions, unknown trip IDs, and non-member requests uniformly return HTTP `404` so trip UUIDs cannot be enumerated (`tests/api/test_route_authz.py`).
- **TOCTOU re-verification (`app/services/trip_guards.py`):** Write operations acquire the PostgreSQL trip row lock (`FOR NO KEY UPDATE` or `FOR SHARE`) via `lock_trip_for_actor()` and re-check `require_active_caller()` and lock/closed state under that lock.
- **Public UUIDs:** All trip, member, expense, contribution, and payment identifiers are random UUIDv4 values with zero sequential integer IDs exposed.

### 3. Session Theft & Cross-Site Request Forgery (CSRF)

- **Hardened device cookies (`app/core/config.py`, `app/api/deps.py`):** Outside development (`VALLET_COOKIE_SECURE=true`), sessions use the `__Host-vl_device` prefix with `HttpOnly`, `Secure`, `SameSite=Lax`, `Path=/`, and no `Domain` attribute so sibling subdomains cannot plant or overwrite cookies. Session secrets never touch `localStorage`.
- **Hashed tokens & revocation (`app/services/devices.py`, `app/api/devices.py`):** Raw 256-bit tokens (`secrets.token_urlsafe(32)`) are stored solely as SHA-256 digests, expire after `VALLET_DEVICE_TTL_DAYS` (180 days default), and revoke server-side on `POST /devices/me/sign-out` or leaving a trip.
- **Dual CSRF defense (`app/api/csrf.py`):** State-changing HTTP methods (`POST`, `PUT`, `PATCH`, `DELETE`) require both `X-Requested-With: vallet` (triggering CORS preflight rejection across origins) and an `Origin` header present in `VALLET_ALLOWED_ORIGINS`.

### 4. Cross-Site Scripting (XSS) & HTTP Security Headers

- **Safe rendering (`frontend/src/`):** All names, titles, notes, and places render as plain Vue text bindings (zero `v-html`). Location links (`mapsUrl()` in `ExpenseDetailBody.vue`) are constructed by the app with `rel="noopener noreferrer"` rather than accepting arbitrary URLs.
- **Strict Content Security Policy (`infra/nginx.conf`, `vercel.json`, `app/api/security_headers.py`):**
  - Static frontend edge headers enforce `Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'`, `Referrer-Policy: no-referrer`, `X-Content-Type-Options: nosniff`, and `Permissions-Policy: camera=(), microphone=(), geolocation=()`. In `vercel.json`, frontend headers are scoped to `/((?!api(?:/|$)).*)` so `/api/*` traffic preserves API headers untouched.
  - Every API JSON response (including 403/413/422/429/500 responses via outermost `SecurityHeadersMiddleware` and `register_error_handlers`) carries `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `Cross-Origin-Resource-Policy: same-site`, and HSTS (`max-age=31536000; includeSubDomains`) when `cookie_secure` is enabled.

### 5. Injection, Input Validation & Financial Integrity

- **Parameterized SQL:** All database reads and writes execute through SQLAlchemy 2 bound parameters and typed ORM queries; no string-interpolated SQL exists.
- **Strict Pydantic schemas:** Request payloads forbid unknown fields (`extra="forbid"`), enforce length/character bounds, and reject out-of-range integer amounts. Validation errors return field locations only (`fields`) without echoing rejected inputs (`app/api/errors.py`).
- **Server-authoritative math (`app/domain/`, `app/services/expenses.py`):** Expenses use integer minor units (`VND` at exponent `0`, `USD` at exponent `2`). The server canonicalizes participant order by member `position`, validates weights/sums, and recomputes every split, balance, and greedy settlement transfer server-side.
- **Concurrency & tamper safeguards:** Money creates accept UUID `Idempotency-Key` headers with payload digest checking (`app/api/idempotency.py`), expense updates enforce optimistic `version` matching (`app/services/expense_edits.py`), deletes are soft, and all expense, fund, lock, link rotation, and bank account changes emit audit `events`.
- **Owner-only bank accounts (`app/api/bank_accounts.py`):** Only `/trips/{trip_id}/members/me/bank-account` exists, preventing any member from altering another member's settlement destination.

### 6. Data at Rest, Cache Safety & Log Hygiene

- **Authenticated encryption (`app/core/crypto.py`, `app/services/vietqr.py`):** Beneficiary bank account numbers are encrypted under `VALLET_BANK_DATA_KEY` (32 bytes, base64url) using AES-256-GCM (`version (1 byte) || nonce (12 bytes) || ciphertext + tag`) with row-bound Additional Authenticated Data (`bank_account_aad(trip_id, member_id)`), preventing cross-row or cross-trip ciphertext substitution.
- **Offline cache isolation (`frontend/src/pwa/pwaConfig.ts`, `frontend/src/lib/offlineCache.ts`, `frontend/src/lib/api.ts`):** Workbox runtime caching (`vallet-api-v1`) caches only same-origin `GET /api/trips*` responses, explicitly skipping `/api/join*`, `/share-link`, `/vietqr`, and `Cache-Control: no-store` responses. Responses returning `401` clear the entire `vallet-api-v1` cache (`forgetAllTripCopies`), while `403`/`404` on `/trips/:id*`, leaving a trip, and signing out evict affected cached entries immediately.
- **Log hygiene (`app/core/logging.py`, `tests/api/test_log_hygiene.py`):** `RedactingFilter` strips `Cookie`, `Set-Cookie`, `Authorization` headers, and 43-character token patterns from root and Uvicorn loggers; handlers never log request bodies or secrets; unexpected 500s return only a generic error envelope.

### 7. Abuse Controls, Fail-Closed Configuration & Supply Chain

- **Request & capacity caps (`app/core/limits.py`):** Request bodies are capped at 64 KiB (`BodyLimitMiddleware`); per-resource ceilings enforce 50 active members, 200 total member rows, 50 trips per device, 2,000 live expenses, 1,000 live contributions, and 1,000 live settlement payments.
- **Rate limiting (`app/api/rate_limit.py`):** Bounded LRU token buckets (`10,000` tracked keys per minute window) throttle general traffic (`300/min`), writes (`120/min`), share-token joins/previews (`20/min`), and trip creation (`10/min`).
- **Fail-closed defaults (`app/core/config.py`):** `Settings.environment` defaults to `"production"`, refusing development fallback keys, non-HTTPS `VALLET_ALLOWED_ORIGINS`, loopback/default database URLs, and `VALLET_COOKIE_SECURE=false` outside `development`. OpenAPI/Swagger endpoints (`/docs`, `/redoc`, `/openapi.json`) are disabled outside `development`.
- **Automated CI checks (`.github/workflows/security.yml`):** Pushes and pull requests run `gitleaks` secret scanning across git history, `pip-audit` against hash-pinned `backend/requirements.lock`, `npm audit --omit=dev --audit-level=moderate`, and strict production/dev npm license allowlisting.
