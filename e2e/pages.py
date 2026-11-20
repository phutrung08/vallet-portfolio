"""Explicit-wait page object helpers built around accessible roles, labels, and visible text."""

from __future__ import annotations

import re
from collections.abc import Callable

from selenium.common.exceptions import (
    ElementClickInterceptedException,
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as expected
from selenium.webdriver.support.wait import WebDriverWait

TIMEOUT = 15
DIALOG = "//dialog[@open]"
RETRY_ON = (
    NoSuchElementException,
    StaleElementReferenceException,
    ElementClickInterceptedException,
)


def literal(text: str) -> str:
    """Return an XPath 1.0 string literal for text containing single or double quotes."""
    if "'" not in text:
        return f"'{text}'"
    if '"' not in text:
        return f'"{text}"'
    parts = text.split("'")
    return "concat(" + ', "\'", '.join(f"'{part}'" for part in parts) + ")"


def button(name: str, scope: str = "") -> str:
    """Match a button or link by aria-label, full normalized text, or inner label span."""
    wanted = literal(name)
    return (
        f"{scope}//*[(self::button or self::a) and "
        f"(@aria-label={wanted} or normalize-space(.)={wanted} "
        f"or .//span[normalize-space(.)={wanted}])]"
    )


def field(label: str, scope: str = "") -> str:
    """Locate an input associated with a `<label>` matching `label` via its `for` attribute."""
    return f"{scope}//input[@id=//label[normalize-space(.)={literal(label)}]/@for]"


def text_node(text: str, tag: str = "*", scope: str = "") -> str:
    """Locate an element whose normalized text equals `text`."""
    return f"{scope}//{tag}[normalize-space(.)={literal(text)}]"


def containing(text: str, tag: str = "*", scope: str = "") -> str:
    return f"{scope}//{tag}[contains(normalize-space(.), {literal(text)})]"


def row(title: str) -> str:
    """Locate an expense list row by its visible title."""
    return f"//li[.//span[normalize-space(.)={literal(title)}]]"


def toggle_button(name: str) -> str:
    """Locate a pressable toggle chip (`aria-pressed`) showing `name`."""
    return f"//button[@aria-pressed and .//span[normalize-space(.)={literal(name)}]]"


class Screen:
    """Browser window wrapper providing race-free explicit waits."""

    def __init__(self, driver: WebDriver, base_url: str) -> None:
        self.driver = driver
        self.base_url = base_url

    def wait(self, timeout: float = TIMEOUT) -> WebDriverWait[WebDriver]:
        return WebDriverWait(self.driver, timeout, ignored_exceptions=RETRY_ON)

    def open(self, path: str) -> None:
        self.driver.get(path if path.startswith("http") else f"{self.base_url}{path}")

    def visible(self, xpath: str) -> WebElement:
        return self.wait().until(expected.visibility_of_element_located((By.XPATH, xpath)))

    def gone(self, xpath: str) -> None:
        self.wait().until(expected.invisibility_of_element_located((By.XPATH, xpath)))

    def count(self, xpath: str) -> int:
        return len(self.driver.find_elements(By.XPATH, xpath))

    def text(self, xpath: str) -> str:
        return self.visible(xpath).text

    def wait_text(self, xpath: str, expected_text: str) -> None:
        """Wait until element text contains `expected_text`, re-querying on every poll."""

        def holds(driver: WebDriver) -> bool:
            return expected_text in driver.find_element(By.XPATH, xpath).text

        self.wait().until(holds)

    def wait_until(self, condition: Callable[[WebDriver], object]) -> None:
        self.wait().until(condition)

    def wait_url(self, pattern: str) -> re.Match[str]:
        def matched(driver: WebDriver) -> re.Match[str] | None:
            return re.search(pattern, driver.current_url)

        return self.wait().until(matched)

    def click(self, xpath: str) -> None:
        last_error: list[str] = []

        def attempt(driver: WebDriver) -> bool:
            try:
                element = driver.find_element(By.XPATH, xpath)
                if not (element.is_displayed() and element.is_enabled()):
                    last_error[:] = ["not displayed or not enabled"]
                    return False
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'})", element)
                element.click()
            except RETRY_ON as error:
                last_error[:] = [f"{type(error).__name__}: {str(error).splitlines()[0]}"]
                return False
            return True

        try:
            self.wait().until(attempt)
        except TimeoutException:
            raise TimeoutException(f"click {xpath} failed: {last_error}") from None

    def type(self, xpath: str, text: str) -> None:
        self.click(xpath)
        self.visible(xpath).send_keys(text)

    def replace(self, xpath: str, text: str) -> None:
        """Select existing input value and overwrite it via keystrokes."""
        self.click(xpath)
        element = self.visible(xpath)
        element.send_keys(Keys.CONTROL, "a")
        element.send_keys(text)

    def clear(self, xpath: str) -> None:
        self.click(xpath)
        element = self.visible(xpath)
        element.send_keys(Keys.CONTROL, "a", Keys.BACKSPACE)

    def wait_value(self, xpath: str, value: str) -> None:
        def holds(driver: WebDriver) -> bool:
            return driver.find_element(By.XPATH, xpath).get_attribute("value") == value

        self.wait().until(holds)

    def set_date(self, xpath: str, iso: str) -> None:
        """Set a native date input value consistently regardless of OS locale date formatting."""
        element = self.visible(xpath)
        self.driver.execute_script(
            "const setter = Object.getOwnPropertyDescriptor("
            "HTMLInputElement.prototype, 'value').set;"
            "setter.call(arguments[0], arguments[1]);"
            "arguments[0].dispatchEvent(new Event('input', {bubbles: true}));"
            "arguments[0].dispatchEvent(new Event('change', {bubbles: true}));",
            element,
            iso,
        )
        self.wait_value(xpath, iso)

    def current_path(self) -> str:
        return str(self.driver.execute_script("return location.pathname + location.search"))
