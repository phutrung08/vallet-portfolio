# Architecture Overview

Vallet is a mobile-first Progressive Web App (PWA) for splitting group travel expenses, tracking an optional shared fund, and settling balances via VietQR transfers. It is structured as a modular monolith backend paired with a strict TypeScript Vue 3 Single-Page Application.

## System Topology

```text
Browser / Installed PWA (Vue 3 + Workbox)
  │
  ├─► Same-origin Edge (Nginx / Vercel / Vite) ────► Static SPA bundle + precached assets
  │                                                    └─ Frontend CSP & security headers
  │
  └─► Same-origin API (/api/*) ────────────────────► FastAPI ASGI app (uvicorn or Vercel api/index.py)
                                                       ├─ Edge Middleware
                                                       │   ([StripPrefix] -> SecurityHeaders -> RateLimit -> BodyLimit -> Csrf)
                                                       ├─ Routers (app/api/*)
                                                       ├─ Services (app/services/*)
                                                       ├─ Pure Domain (app/domain/*)
                                                       └─ Repositories & ORM (app/repositories/*) ──► PostgreSQL 18 / Neon
```

Vallet supports both containerized Nginx + Uvicorn hosting (`infra/nginx.conf` + `docker-compose.yml`), single-project fullstack Vercel hosting (`vercel.json` + `api/index.py` + `StripPrefixMiddleware`), and an optional standalone portfolio demo mode built with `VITE_DEMO_ONLY=true` (`frontend/src/features/demo/demoSource.ts`) with no backend required.

## Backend Modular Monolith (`backend/app`)

Layer dependencies are strictly unidirectional and verified by AST static checks in `backend/tests/test_architecture.py`:

```text
app.api ──► app.services ──► app.domain (stdlib only; zero I/O or ORM imports)
                │
                ▼
         app.repositories ──► PostgreSQL 18 (SQLAlchemy 2 async + asyncpg)

app.core (config, crypto, db, limits, logging, security) — imported downward only
app.jobs (cleanup tasks) — invokes app.services / app.repositories
```

Key architectural invariants enforced by `tests/test_architecture.py`:

- `app.domain` may import only Python stdlib modules and other `app.domain` submodules (`money.py`, `split.py`, `balance.py`, `settle.py`, `vietqr.py`, `banks.py`, `ascii_text.py`, `constants.py`).
- `app.api` cannot import `app.repositories` or `app.domain` directly; routers delegate all orchestration to `app.services`.
- `app.repositories` and `app.core` cannot import higher layers (`services`, `api`, `jobs`, `main`).
- Production modules under `backend/app/` must contain zero `assert` statements and zero `type: ignore` suppressions.

### Exact Integer Money & Deterministic Domain Math

All monetary amounts are represented strictly as integer minor units (`VND` at exponent `0`, `USD` at exponent `2`) with zero floating-point arithmetic:

- **Proportional allocation (`app/domain/money.py`):** `allocate(total, weights)` uses exact floor division (`total * w // weight_sum`) and assigns leftover minor units deterministically via largest remainder (`total * w % weight_sum`), breaking ties by member order.
- **Expense splits (`app/domain/split.py`, `app/services/expenses.py`):** Supports `equal`, `shares`, `percent` (basis points), and `exact` modes. `order_by_position()` canonicalizes participant weights by member `position` so remainder distribution never depends on client JSON key ordering. Client-supplied per-member amounts are rejected unless recomputed shares reconcile cleanly.
- **Balances & settlement (`app/domain/balance.py`, `app/domain/settle.py`):** Computes per-member `paid`, `contributed`, `share`, `sent`, `received`, and `net` balances plus remaining shared fund balance. `settle(nets)` applies a min-heap greedy transfer matcher yielding at most $k - 1$ deterministic transfers for $k$ non-zero members.
- **Server-computed trip summary (`app/api/balances.py` -> `app/services/summary.py`):** `GET /trips/{trip_id}/summary` aggregates daily totals, category percentages (allocated to 100 via `allocate`), per-payer totals, and per-person/per-day averages in four constant SQL queries, eliminating client-side N+1 day fetches.

### Concurrency, Locking & Auditability

Multi-user writes on shared trips coordinate cleanly through PostgreSQL row locking, optimistic concurrency control, and idempotency:

- **Two-tier row locking (`app/repositories/trips.py`, `app/services/trip_guards.py`):**
  - `lock_trip` acquires `SELECT ... FOR NO KEY UPDATE` on the target trip row for membership mutations, capacity-bounded inserts (`create_expense`, `add_contribution`, holder changes), joins, and trip state transitions without blocking foreign-key `FOR KEY SHARE` checks.
  - `share_lock_trip` acquires `SELECT ... FOR SHARE` for row-scoped mutations (expense edits/deletes, contribution deletion, bank account updates, payments) so concurrent expense edits do not serialize unnecessarily while remaining blocked against concurrent lock/membership changes.
  - Both paths run `require_active_caller()` **after** acquiring the lock to eliminate TOCTOU privilege races when a caller is concurrently removed or the trip is locked/closed.
- **Optimistic versioning & idempotency:** Expense edits require `expected_version` (`version_conflict` -> HTTP `409` on mismatch). Money-recording creates (`POST /trips/{trip_id}/expenses`, contributions, payments) accept an optional `Idempotency-Key` UUID header (`app/api/idempotency.py`), deduplicating retries per `(device_id, key)` with payload digest verification and `Idempotent-Replayed: true`.
- **Append-only audit log & soft deletes:** Trips keep an `events` timeline of membership, fund holder, expense, settlement, bank update, and lock/close actions; removed members and soft-deleted expenses retain referential history while preserving aggregate accuracy.

### Edge & Persistence

- **ASGI middleware stack (`app/main.py`):** Ordered outermost-to-innermost as optional `StripPrefixMiddleware` (`app/api/prefix.py`, used by Vercel `api/index.py`) -> `SecurityHeadersMiddleware` -> `RateLimitMiddleware` -> `BodyLimitMiddleware` -> `CsrfMiddleware`, ensuring `/api/*` rewrites and even rejected requests (413, 429, 403, 500) receive strict security headers.
- **Database schema & pooling (`app/core/db.py`, `app/core/config.py`, `migrations/env.py`):** Foreign keys use `DEFERRABLE` constraints on member references (`get_db` maps commit `IntegrityError` to HTTP `409`) and indexed SHA-256 hashes for device sessions and share links. `normalize_asyncpg_url()` adapts `postgres://` / `postgresql://`, `sslmode`, and `channel_binding` query params cleanly for `asyncpg`; setting `VALLET_DB_NULL_POOL=true` (enabled automatically by `configure_vercel_env()` in `api/index.py`) uses `NullPool` with prepared statement caches disabled for PgBouncer / Neon `-pooler` compatibility.
- **Edge header scoping (`vercel.json`, `infra/nginx.conf`):** Vercel rewrites `/api` and `/api/*` to `api/index.py` before the SPA `/index.html` fallback and excludes `/api` paths from static HTML CSP headers so API responses keep FastAPI's `default-src 'none'` policy.

## Frontend Architecture (`frontend/src`)

The frontend uses Vue 3 `<script setup lang="ts">` with strict `vue-tsc` type checking and modular feature directories under `frontend/src/features/`:

- `activity/` — trip event feed (`ActivityView`, `ActivityRow`, `activityKinds.ts`)
- `balances/` — net balance breakdown, settled payment history, and VietQR settlement sheet (`BalancesView`, `TransferSheet`, `TransferPanel`, `QrDetails`)
- `bank/` — beneficiary bank selection and encrypted account update form (`BankAccountSheet`, `BankAccountForm`, `BankPicker.vue`, `useBankAccountForm.ts`)
- `demo/` — self-contained offline fixture & read-only trip data source (`demoTrip.json`, `demoSource.ts`, `DemoLayout.vue`)
- `expenses/` — day tabs, expandable split rows, expense create/edit form (`ExpenseForm`, `SplitModeEditor`, `AmountInput`, `ExpenseDetailPane`)
- `fund/` — optional shared fund balance, contributions, and fund-holder transfer (`FundView`)
- `join/` — URL hash-fragment invite preview & claim/join workflow (`JoinView`)
- `members/` — active/removed member management, share link rotation, lock/close/leave controls (`MembersView`)
- `settings/` — theme appearance (`light` / `dark` / `system`), adaptive nav placement, language switcher (`en` default / `vi`), and device sign-out (`SettingsView`)
- `shell/` — fallback route handling (`NotFoundView`)
- `summary/` — trip spend totals, category distribution bars, and payer leaderboard (`TripSummaryView`, `TripStatsPane`)
- `trips/` — device trip list, trip creation wizard, and split overview (`HomeView`, `CreateTripView`, `TripView`)

### UI Primitives, Navigation & Responsive Split Layout

- **Lightweight Composition API architecture:** State management and interactions are built with focused Vue 3 Composition API composables (`tripSource.ts`, `useNavPlacement`, `useNavDrag`, `useModalBehavior`, `usePullToRefresh`) and Tailwind CSS 4 design tokens rather than heavy runtime frameworks.
- **Native `<dialog>` sheets (`BottomSheet.vue`, `ConfirmSheet.vue`):** Modals use native `<dialog>` with `closedby="any"` (`Escape` / backdrop dismissal), focus management, and scroll-padding clearance.
- **Adaptive navigation (`BottomNav.vue`, `NavDragLayer.vue`, `styles/nav.css`):** Switches smoothly between centered compact bottom dock, movable left/bottom/right large-phone dock (`--breakpoint-phone-lg: 25rem`), and vertical left/right rail (`--breakpoint-rail: 37.5rem`), with press-and-hold drag repositioning persisted in `localStorage`.
- **Two-pane & foldable split layout (`SplitLayout.vue`, `styles/split.css`, `tokens.css`):** Activates dual side-by-side scrolling panes at `--breakpoint-split: 42rem` (`672px`) and enhances via CSS Viewport Segments media queries (`horizontal-viewport-segments: 2` and `vertical-viewport-segments: 2`) so split panes never straddle hardware fold hinges.

### Offline PWA & Cache Eviction

- **Workbox runtime caching (`frontend/src/pwa/pwaConfig.ts` -> `vite.config.ts`):** Precaching is combined with a `NetworkFirst` policy (`vallet-api-v1`, 4 s timeout, 300 entries, 30-day max age) limited strictly to same-origin `GET /api/trips*` requests. Share-link tokens, `/api/join*`, `/vietqr*`, and responses carrying `Cache-Control: no-store` are explicitly excluded from caching.
- **Prompted SW updates & offline indicator (`App.vue`, `OfflineBanner.vue`, `UpdateToast.vue`, `CachedNotice.vue`):** Responses served from cache carry an `X-Served-From: cache` header so views display a timestamped cached-copy indicator.
- **Auth-error cache eviction (`frontend/src/lib/offlineCache.ts`, `frontend/src/lib/api.ts`):** Any `401` response purges the entire `vallet-api-v1` cache (`forgetAllTripCopies`), while `403`/`404` on `/trips/{tripId}*`, leaving a trip, or signing out evicts that trip's cached API responses (`evictTripCacheOnAuthError` / `forgetTripCopy`).

## Verification & CI Pipeline

- **Continuous Integration (`.github/workflows/ci.yml`):** Runs `ruff check`, `ruff format --check`, `mypy app`, and `pytest` against PostgreSQL 18 on the backend, alongside `eslint --max-warnings 0`, `vue-tsc --noEmit`, `vitest run`, and `vite build` on the frontend.
- **Security Automation (`.github/workflows/security.yml`):** Enforces git secret scanning (`gitleaks`), Python dependency vulnerability checks (`pip-audit`), `npm audit --omit=dev --audit-level=moderate`, and strict production/dev license allowlists.
- **End-to-End & Accessibility (`e2e/`):** Selenium WebDriver tests validate full multi-user trip, settle, and share-link rotation journeys (`test_trip_flow.py`, `test_join_settle.py`), adaptive nav dragging (`test_adaptive_nav.py`), responsive layout across emulated foldables/tablets (`test_device_matrix.py`), and `axe-core` WCAG 2.1 Level A & AA audits (`test_accessibility.py`).
