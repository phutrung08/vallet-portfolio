"""Pytest + Selenium E2E fixtures driving mobile-emulated headless Chrome against real servers."""

from __future__ import annotations

import os
import re
import shutil
import sys
import tempfile
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
import servers
from pages import Screen
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.remote.webdriver import WebDriver

SCREENSHOT_DIR = Path(__file__).resolve().parent / "screenshots"
MOBILE_USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/130.0.0.0 Mobile Safari/537.36"
)
DEVICE_METRICS = {"width": 375, "height": 812, "pixelRatio": 2.0}


@pytest.fixture(scope="session")
def e2e_servers(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    """Reset the E2E database, start FastAPI + Vite dev proxy, and yield the app base URL."""
    logs = tmp_path_factory.mktemp("logs")
    servers.reset_database()
    started: list[servers.ManagedProcess] = []
    try:
        backend = servers.start_backend(logs / "backend.log")
        started.append(backend)
        frontend = servers.start_frontend(logs / "frontend.log")
        started.append(frontend)
        backend.wait_until_serving(f"{servers.BACKEND_URL}/health")
        frontend.wait_until_serving(f"{servers.FRONTEND_URL}/")
        yield servers.FRONTEND_URL
    finally:
        for process in reversed(started):
            process.stop()


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[None]) -> Iterator[None]:
    report = yield
    if report.when == "call":
        item.stash[_FAILED] = report.failed
    return report


_FAILED = pytest.StashKey[bool]()


def _chrome_options(profile: Path, headed: bool) -> Options:
    options = Options()
    if not headed:
        options.add_argument("--headless=new")
    options.add_argument(f"--user-data-dir={profile}")
    options.add_argument("--lang=en")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    options.add_argument("--disable-search-engine-choice-screen")
    if sys.platform.startswith("linux"):
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
    options.add_experimental_option("prefs", {"intl.accept_languages": "en,en-US"})
    options.add_experimental_option(
        "mobileEmulation", {"deviceMetrics": DEVICE_METRICS, "userAgent": MOBILE_USER_AGENT}
    )
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    return options


def _new_driver(profile: Path, headed: bool) -> WebDriver:
    driver = webdriver.Chrome(options=_chrome_options(profile, headed))
    driver.set_page_load_timeout(30)
    driver.set_script_timeout(15)
    # Disable CSS transitions so opening sheets and dialogs settles immediately.
    driver.execute_cdp_cmd(
        "Emulation.setEmulatedMedia",
        {"features": [{"name": "prefers-reduced-motion", "value": "reduce"}]},
    )
    return driver


@pytest.fixture
def browser(
    request: pytest.FixtureRequest, e2e_servers: str, tmp_path_factory: pytest.TempPathFactory
) -> Iterator[Callable[[], Screen]]:
    """Open an isolated Chrome profile per call (representing an independent user device)."""
    headed = os.environ.get("E2E_HEADED") == "1"
    opened: list[tuple[WebDriver, Path]] = []

    def make() -> Screen:
        profile = Path(tempfile.mkdtemp(prefix="vallet-e2e-profile-"))
        driver = _new_driver(profile, headed)
        opened.append((driver, profile))
        return Screen(driver, e2e_servers)

    yield make

    failed = request.node.stash.get(_FAILED, False)
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", request.node.nodeid)
    for index, (driver, profile) in enumerate(opened, start=1):
        if failed:
            SCREENSHOT_DIR.mkdir(exist_ok=True)
            driver.save_screenshot(str(SCREENSHOT_DIR / f"{safe_name}-device{index}.png"))
        driver.quit()
        shutil.rmtree(profile, ignore_errors=True)
