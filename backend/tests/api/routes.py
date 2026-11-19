"""Walk the routes an app actually serves, for tests that must cover new routes automatically."""

from collections.abc import Iterable, Iterator
from typing import Any

from fastapi import FastAPI
from fastapi.dependencies.models import Dependant


def served_routes(app: FastAPI) -> Iterator[tuple[str, str, Dependant]]:
    """Yield every ``(method, path, dependant)`` of the app's HTTP routes with prefixes applied."""
    for route in app.routes:
        # FastAPI includes routers lazily; the effective contexts carry the prefixed path and
        # the dependency tree as served.
        flat: Iterable[Any] = (
            route.effective_route_contexts()
            if hasattr(route, "effective_route_contexts")
            else [route]
        )
        for served in flat:
            path: str = getattr(served, "path", "")
            if not path or getattr(served, "dependant", None) is None:
                continue
            for method in sorted(served.methods):
                yield method, path, served.dependant
