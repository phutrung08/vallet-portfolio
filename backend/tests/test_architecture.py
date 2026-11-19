"""Automated architectural boundary guards across backend layers."""

import ast
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "app"


def _layer_files(layer: str) -> list[Path]:
    return sorted((APP_DIR / layer).rglob("*.py"))


def _all_app_files() -> list[Path]:
    return sorted(APP_DIR.rglob("*.py"))


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def _assert_no_forbidden_prefixes(layer: str, forbidden: tuple[str, ...]) -> None:
    violations: list[str] = []
    for path in _layer_files(layer):
        for module in _imported_modules(path):
            if any(module == prefix or module.startswith(f"{prefix}.") for prefix in forbidden):
                violations.append(f"{path.relative_to(APP_DIR)} imports {module}")
    assert not violations, f"Layer boundary violations in {layer}: {violations}"


def test_domain_imports_only_stdlib_and_domain() -> None:
    violations: list[str] = []
    for path in _layer_files("domain"):
        for module in _imported_modules(path):
            top = module.split(".")[0]
            if module == "app.domain" or module.startswith("app.domain."):
                continue
            if top in sys.stdlib_module_names:
                continue
            violations.append(f"{path.relative_to(APP_DIR)} imports {module}")
    assert not violations, f"Domain purity violations: {violations}"


def test_api_does_not_import_repositories_or_domain() -> None:
    _assert_no_forbidden_prefixes("api", ("app.repositories", "app.domain"))


def test_repositories_do_not_import_services_api_jobs_or_main() -> None:
    _assert_no_forbidden_prefixes(
        "repositories", ("app.services", "app.api", "app.jobs", "app.main")
    )


def test_core_does_not_import_higher_layers() -> None:
    _assert_no_forbidden_prefixes(
        "core", ("app.repositories", "app.services", "app.api", "app.jobs", "app.main")
    )


def test_no_assert_statements_in_production_app() -> None:
    found: list[str] = []
    for path in _all_app_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Assert):
                found.append(f"{path.relative_to(APP_DIR)}:{node.lineno}")
    assert not found, f"Production code must not contain assert statements: {found}"


def test_no_type_ignore_comments_in_production_app() -> None:
    found: list[str] = []
    for path in _all_app_files():
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if "type: ignore" in line:
                found.append(f"{path.relative_to(APP_DIR)}:{lineno}")
    assert not found, f"Production code must not contain type: ignore: {found}"
