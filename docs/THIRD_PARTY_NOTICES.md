# Third-Party Notices

This repository includes original source code licensed under [`LICENSE`](../LICENSE) along with declarations referencing third-party open-source packages installed during build and deployment. Each third-party component remains licensed under its respective upstream terms.

## Frontend Runtime Dependencies (`frontend/package.json`)

| Package | Version Range | License | Purpose |
|---|---|---|---|
| `vue` | `^3.5.45` | MIT | UI component runtime and reactivity system |
| `vue-router` | `^5.5.1` | MIT | Client-side routing and pane query synchronization |
| `vue-i18n` | `^11.4.20` | MIT | English and Vietnamese localization messages and pluralization |
| `lucide-vue-next` | `^1.0.0` | ISC | Crisp UI stroke iconography |
| `qrcode` | `^1.5.4` | MIT | Client-side canvas rendering of VietQR payloads |
| `workbox-window` | `^7.4.1` | MIT | Service worker lifecycle registration and update prompting |
| `@fontsource/baloo-2` | `^5.3.0` | OFL-1.1 | Self-hosted `Baloo 2` display heading webfont |
| `@fontsource/be-vietnam-pro` | `^5.3.0` | OFL-1.1 | Self-hosted `Be Vietnam Pro` body webfont |

## Backend Runtime Dependencies (`backend/pyproject.toml`)

| Package | Version Constraint | License | Purpose |
|---|---|---|---|
| `fastapi` | `>=0.162,<1` | MIT | ASGI web API framework and OpenAPI schema generation |
| `uvicorn[standard]` | `>=0.54,<1` | BSD-3-Clause | High-performance ASGI server |
| `pydantic` / `pydantic-settings` | `>=2.16,<3` | MIT | Strict schema validation and fail-closed env settings |
| `sqlalchemy[asyncio]` | `>=2.1.8,<2.2` | MIT | Async ORM and parameterized SQL builder |
| `asyncpg` | `>=0.32,<1` | Apache-2.0 | Asynchronous PostgreSQL wire protocol driver |
| `alembic` | `>=1.20,<2` | MIT | Versioned relational database schema migrations |
| `cryptography` | `>=50.0,<51` | Apache-2.0 OR BSD-3-Clause | AES-256-GCM authenticated encryption primitives |

## License Policy & Verification

- Production frontend dependencies are restricted in CI ([`.github/workflows/security.yml`](../.github/workflows/security.yml)) to permissive OSI/font licenses (`MIT`, `Apache-2.0`, `BSD-2-Clause`, `BSD-3-Clause`, `ISC`, `OFL-1.1`, `0BSD`, `Unlicense`).
- Build/test-only development dependencies (including Tailwind CSS, Vite, Vitest, ESLint, Selenium, pytest, ruff, mypy, and `axe-core` under `MPL-2.0`) are audited and pinned in [`frontend/package-lock.json`](../frontend/package-lock.json), [`backend/requirements-dev.lock`](../backend/requirements-dev.lock), [`backend/requirements.lock`](../backend/requirements.lock), and [`e2e/requirements.txt`](../e2e/requirements.txt).
