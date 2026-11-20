"""Process lifecycle management for E2E tests: PostgreSQL reset, FastAPI backend, and Vite dev."""

from __future__ import annotations

import os
import shutil
import signal
import socket
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import IO, Any

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.wait import WebDriverWait

ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT / "backend"

DB_NAME = "vallet_e2e"
DB_HOST = os.environ.get("E2E_DB_HOST", "127.0.0.1")
DB_PORT = os.environ.get("E2E_DB_PORT", "5433")
DB_USER = os.environ.get("E2E_DB_USER", "vallet")
DB_PASSWORD = os.environ.get("E2E_DB_PASSWORD", "vallet_dev")  # noqa: S105 - local dev database

BACKEND_PORT = 8765
FRONTEND_PORT = 5174
BACKEND_URL = f"http://127.0.0.1:{BACKEND_PORT}"
FRONTEND_URL = f"http://127.0.0.1:{FRONTEND_PORT}"
DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

STARTUP_TIMEOUT = 90

# Runs via backend virtualenv (which already bundles asyncpg) so e2e/.venv stays minimal.
_RESET_DATABASE = """
import asyncio
import sys

import asyncpg


async def main(host, port, user, password, name):
    connection = await asyncpg.connect(
        host=host, port=int(port), user=user, password=password, database="postgres", timeout=10
    )
    try:
        await connection.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        await connection.execute(f'CREATE DATABASE "{name}"')
    finally:
        await connection.close()


asyncio.run(main(*sys.argv[1:]))
"""


def backend_python() -> str:
    """Return the backend Python executable (overridable via E2E_BACKEND_PYTHON)."""
    override = os.environ.get("E2E_BACKEND_PYTHON")
    if override:
        return override
    folder = "Scripts" if os.name == "nt" else "bin"
    suffix = ".exe" if os.name == "nt" else ""
    path = BACKEND_DIR / ".venv" / folder / f"python{suffix}"
    if not path.exists():
        raise RuntimeError(f"Backend virtualenv not found at {path}; set E2E_BACKEND_PYTHON.")
    return str(path)


def backend_env() -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "VALLET_DATABASE_URL": DATABASE_URL,
            "VALLET_COOKIE_SECURE": "false",
            "VALLET_ALLOWED_ORIGINS": f'["{FRONTEND_URL}"]',
            "VALLET_ENVIRONMENT": "development",
        }
    )
    return env


def reset_database() -> None:
    """Drop and recreate the E2E database, then run Alembic migrations to head."""
    python = backend_python()
    reset = subprocess.run(  # noqa: S603
        [python, "-c", _RESET_DATABASE, DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if reset.returncode != 0:
        raise RuntimeError(
            f"Cannot reset database {DB_NAME} on {DB_HOST}:{DB_PORT} "
            f"(is `docker compose up -d db` running?):\n{reset.stderr[-1500:]}"
        )
    migrate = subprocess.run(  # noqa: S603
        [python, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
        env=backend_env(),
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if migrate.returncode != 0:
        raise RuntimeError(f"Alembic upgrade failed:\n{migrate.stderr[-1500:]}")


def assert_port_free(port: int) -> None:
    with socket.socket() as probe:
        probe.settimeout(1)
        if probe.connect_ex(("127.0.0.1", port)) == 0:
            raise RuntimeError(f"Port {port} is already in use; stop that process and retry.")


class ManagedProcess:
    """Subprocess running in its own process group so teardown kills the entire tree."""

    def __init__(
        self, name: str, args: list[str], cwd: Path, env: dict[str, str], log: Path
    ) -> None:
        self.name = name
        self.log_path = log
        self._log: IO[bytes] = log.open("wb")
        options: dict[str, Any] = {}
        if os.name == "nt":
            options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            options["start_new_session"] = True
        self.process = subprocess.Popen(  # noqa: S603
            args,
            cwd=cwd,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=self._log,
            stderr=subprocess.STDOUT,
            **options,
        )

    def log_tail(self, chars: int = 2000) -> str:
        self._log.flush()
        return self.log_path.read_text(errors="replace")[-chars:]

    def stop(self) -> None:
        if self.process.poll() is None:
            self._kill_tree()
            try:
                self.process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.process.kill()
        self._log.close()

    def _kill_tree(self) -> None:
        if os.name == "nt":
            taskkill = shutil.which("taskkill") or "taskkill"
            subprocess.run(  # noqa: S603
                [taskkill, "/PID", str(self.process.pid), "/T", "/F"],
                capture_output=True,
                check=False,
            )
            return
        try:
            os.killpg(self.process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(self.process.pid, signal.SIGKILL)

    def wait_until_serving(self, url: str) -> None:
        def ready(_: object) -> bool:
            if self.process.poll() is not None:
                raise RuntimeError(f"{self.name} exited early:\n{self.log_tail()}")
            try:
                with urllib.request.urlopen(url, timeout=3) as response:  # noqa: S310
                    return bool(response.status == 200)
            except (urllib.error.URLError, OSError):
                return False

        try:
            WebDriverWait(None, STARTUP_TIMEOUT, poll_frequency=0.25).until(ready)  # type: ignore[arg-type]
        except TimeoutException:
            raise RuntimeError(f"{self.name} did not serve {url}:\n{self.log_tail()}") from None


def start_backend(log: Path) -> ManagedProcess:
    assert_port_free(BACKEND_PORT)
    args = [
        backend_python(),
        "-m",
        "uvicorn",
        "app.main:app",
        "--app-dir",
        "backend",
        "--host",
        "127.0.0.1",
        "--port",
        str(BACKEND_PORT),
    ]
    return ManagedProcess("backend", args, ROOT, backend_env(), log)


def start_frontend(log: Path) -> ManagedProcess:
    assert_port_free(FRONTEND_PORT)
    npm = shutil.which("npm")
    if npm is None:
        raise RuntimeError("npm is not on PATH.")
    env = os.environ.copy()
    env["VALLET_API_PROXY"] = BACKEND_URL
    args = [
        npm,
        "--prefix",
        "frontend",
        "run",
        "dev",
        "--",
        "--host",
        "127.0.0.1",
        "--port",
        str(FRONTEND_PORT),
        "--strictPort",
    ]
    return ManagedProcess("frontend", args, ROOT, env, log)
