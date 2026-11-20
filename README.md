# Vallet

**Vallet** is a mobile-first Progressive Web App (PWA) for splitting group travel expenses, tracking an optional shared trip fund, and settling net balances with minimal VietQR bank transfers.

Built as a production-grade full-stack engineering case study: exact integer minor-unit accounting, PostgreSQL row-level concurrency control, security-by-design authentication and encryption, adaptive foldable/tablet layouts, offline-readable caching, and automated WCAG 2.1 Level A & AA verification.

## Highlights

- **Exact Integer Accounting (`VND` & `USD`):** Zero floating-point math. Splits support equal, shares, percentage (basis points), and exact modes using largest-remainder integer allocation (`allocate`) ordered deterministically by member position (`VND` at exponent `0`, `USD` at exponent `2`).
- **Shared Trip Fund & Minimal Settlement:** Optional shared fund with transferable fund holder, contribution tracking, and greedy min-heap settlement producing at most $k - 1$ deterministic transfers for $k$ non-zero participants.
- **VietQR Settlement Sheets:** Decrypts a payee's stored bank account in memory to generate EMVCo VietQR payloads with masked last-4 account confirmation, `Cache-Control: no-store`, and owner-only account management.
- **Offline-Readable PWA & Standalone `/demo` Mode:** Workbox `NetworkFirst` caching (`vallet-api-v1`) keeps trip views readable offline with timestamped cache notices and automatic eviction on `401`/`403`/`404`, leave, or sign-out. Building with `VITE_DEMO_ONLY=true` ships an interactive static `/demo` experience (`Phu Quoc 3D2N`) with zero backend required.
- **Adaptive Mobile, Foldable & Tablet UX:** Bilingual (`en` default / `vi`), light/dark/system theming, native `<dialog closedby="any">` sheets, press-and-hold draggable navigation dock/rail, and a two-pane split layout supporting CSS Viewport Segments (`horizontal-viewport-segments: 2`).

## Architecture

```text
Browser / Installed PWA (Vue 3 + TypeScript + Workbox)
  │
  ├─► Same-origin Reverse Proxy / Static Edge (/) ──► SPA bundle + CSP / security headers
  │
  └─► Same-origin API (/api/*) ────────────────────► FastAPI ASGI Modular Monolith
                                                       ├─ Middleware: SecurityHeaders -> RateLimit -> BodyLimit -> Csrf
                                                       ├─ api/ ──► services/ ──► domain/ (stdlib-only pure math)
                                                       └─ services/ ──► repositories/ ──► PostgreSQL 18 (asyncpg)
```

Strict unidirectional layer boundaries (`api -> services -> domain` and `services -> repositories`, with zero `assert` or `type: ignore` in `backend/app/`) are enforced automatically by AST checks in [`backend/tests/test_architecture.py`](backend/tests/test_architecture.py).

See [`docs/architecture.md`](docs/architecture.md) for detailed backend modules, database locking, and frontend feature structure.

## Key Engineering Decisions

| Area | Design Choice |
|---|---|
| **Money & Splits** | Integer minor units (`VND` exp `0`, `USD` exp `2`); server recomputes every split, balance, settlement, and `GET /trips/{trip_id}/summary` breakdown (4 constant SQL queries, zero client N+1 day fetches). |
| **Concurrency** | Two-tier PostgreSQL row locks (`FOR NO KEY UPDATE` for membership/capacity writes; `FOR SHARE` for row-scoped edits), TOCTOU active-caller checks under lock, optimistic `version` checks, and UUID `Idempotency-Key` deduplication. |
| **Security** | HMAC-SHA256 share links transmitted strictly in URL fragments (`/join#<token>`) and stored as SHA-256 hashes; `HttpOnly` `__Host-vl_device` cookies; dual CSRF (`X-Requested-With: vallet` + `Origin` allowlist); AES-256-GCM bank encryption with row-bound AAD; fail-closed production config. |
| **Responsive & A11y** | Native `<dialog closedby="any">` sheets, WCAG 2.4.11 focus clearance, CSS Viewport Segments hinge avoidance, and 0-violation `axe-core` WCAG 2.1 Level A & AA audits in headless Chrome. |

Full threat model and controls are documented in [`docs/SECURITY.md`](docs/SECURITY.md).

## Automated Verification & Quality Bar

| Layer | Tooling | Verified Coverage |
|---|---|---|
| **Backend** | `ruff`, `mypy --strict`, `pytest` + PostgreSQL 18 | **1,527 passed** (domain, API, authz isolation, AST boundaries, log hygiene, concurrency, DB constraints, migrations) |
| **Frontend** | `eslint --max-warnings 0`, `vue-tsc`, `vitest`, `vite build` | **887 passed across 78 test files** (0 ESLint warnings, strict TypeScript, Workbox SW build) |
| **End-to-End & A11y** | Selenium WebDriver + headless Chrome + `axe-core` | **11 passed** (full trip & join/settle flows, nav drag, **36 device profiles / 33 unique viewports**, **13-screen WCAG 2.1 Level A & AA audit**) |
| **Supply Chain & CI** | GitHub Actions (`ci.yml`, `security.yml`) | `gitleaks`, `pip-audit` (hash-pinned lockfiles), `npm audit --omit=dev`, OSI/font license allowlist |

See [`docs/devices.md`](docs/devices.md) for the full foldable, dual-screen, and tablet viewport matrix.

## Quickstart

### Option 1: Docker Compose (Full Stack)

```bash
docker compose --profile fullstack up --build
```

The application is served at `http://localhost:8080` behind Nginx (proxying `/api/*` to FastAPI and PostgreSQL 18).

### Option 2: Local Development

1. **Start PostgreSQL 18:**
   ```bash
   docker compose up -d db
   ```
2. **Run the FastAPI backend:**
   ```bash
   cd backend
   cp .env.example .env
   python -m venv .venv
   # Activate .venv, then install hash-pinned dev dependencies:
   pip install --require-hashes -r requirements-dev.lock
   pip install --no-deps -e .
   alembic upgrade head
   uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
   ```
3. **Run the Vue 3 frontend:**
   ```bash
   cd frontend
   npm ci
   npm run dev
   ```
   Open `http://localhost:5173`. Vite proxies `/api/*` to `http://127.0.0.1:8000`.

### Option 3: Static Portfolio Demo Build (No Backend)

```bash
cd frontend
npm ci
VITE_DEMO_ONLY=true npm run build
```

Root `vercel.json` configures static `/demo` builds on Vercel with SPA rewrites and security headers matching [`infra/nginx.conf`](infra/nginx.conf).

## Running Tests

```bash
# Backend (requires local Postgres container on 127.0.0.1:5433)
cd backend
VALLET_TEST_DATABASE_URL=postgresql+asyncpg://vallet:vallet_dev@127.0.0.1:5433/vallet_test \
VALLET_REQUIRE_DB=1 pytest

# Frontend
cd frontend
npm run lint && npm run typecheck && npm test && npm run build

# End-to-End (Selenium + headless Chrome; spawns isolated backend + Vite servers)
cd e2e
pip install -r requirements.txt
pytest -v
```

## Documentation

- [`docs/architecture.md`](docs/architecture.md) — Modular monolith layers, row locking, frontend feature structure, and PWA caching
- [`docs/SECURITY.md`](docs/SECURITY.md) — Threat model, cryptography, CSRF/cookie hardening, and CI security controls
- [`docs/devices.md`](docs/devices.md) — 36-profile responsive viewport matrix for foldables, Surface Duo, and tablets
- [`docs/THIRD_PARTY_NOTICES.md`](docs/THIRD_PARTY_NOTICES.md) — Direct runtime dependency attributions and license policy
- [`LICENSE`](LICENSE) — Repository portfolio license terms
