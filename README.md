# Vallet

A mobile-first Progressive Web App (PWA) for splitting group travel expenses, tracking optional shared funds, and settling balances with minimal VietQR transfers.

## Tech Stack

- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2 (async), Alembic, PostgreSQL 18
- **Frontend:** Vue 3, TypeScript (strict), Vite, Tailwind CSS 4, vue-i18n, Workbox PWA
- **Testing & CI:** pytest, Vitest, Selenium (mobile & foldable device matrix), GitHub Actions

## Architecture

Modular monolith with unidirectional dependencies:

- `api -> services -> domain` and `services -> repositories`
- `domain/` contains pure integer-arithmetic modules with zero I/O
- Same-origin `/api` reverse proxy with HttpOnly cookie sessions

> Note: Repository setup is in progress. Detailed architecture notes, screenshots, and local quickstart instructions will be added once all modules are in place.
