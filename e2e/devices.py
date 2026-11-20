"""CSS viewport definitions for the responsive layout matrix (see docs/devices.md).

Dimensions are CSS px as Chrome reports them; `hinge` specifies `(x, width)` of a vertical
fold hinge emulated via CDP `Emulation.setDeviceMetricsOverride`.
"""

from __future__ import annotations

from dataclasses import dataclass

from selenium.webdriver.remote.webdriver import WebDriver

SPLIT_MIN_WIDTH = 672  # 42rem (`--breakpoint-split` in tokens.css)


@dataclass(frozen=True)
class Viewport:
    width: int
    height: int
    dpr: float = 2.0
    hinge: tuple[int, int] | None = None

    @property
    def two_panes(self) -> bool:
        return self.width >= SPLIT_MIN_WIDTH or self.hinge is not None


@dataclass(frozen=True)
class Device:
    name: str
    viewport: Viewport
    estimated: bool = False


def _fold(
    name: str, width: int, height: int, dpr: float, *, estimated: bool = False
) -> list[Device]:
    """Emit both flat-unfolded and vertical-hinge Flex viewports for a foldable device."""
    flat = Viewport(width, height, dpr)
    hinged = Viewport(width, height, dpr, hinge=(width // 2, 0))
    return [
        Device(f"{name} unfolded", flat, estimated),
        Device(f"{name} unfolded, hinge", hinged, estimated),
    ]


def _tablet(name: str, width: int, height: int, *, estimated: bool = False) -> list[Device]:
    return [
        Device(f"{name} portrait", Viewport(width, height), estimated),
        Device(f"{name} landscape", Viewport(height, width), estimated),
    ]


DEVICES: list[Device] = [
    Device("Galaxy Z Fold 4 cover", Viewport(344, 882, 2.625)),
    *_fold("Galaxy Z Fold 4", 690, 829, 2.625),
    Device("Galaxy Z Fold 5 cover", Viewport(344, 882, 2.625)),
    *_fold("Galaxy Z Fold 5", 690, 829, 2.625),
    Device("Galaxy Z Fold 6 cover", Viewport(412, 968, 2.625)),
    *_fold("Galaxy Z Fold 6", 744, 860, 2.625),
    Device("Galaxy Z Fold 7 cover", Viewport(411, 960, 2.625), estimated=True),
    *_fold("Galaxy Z Fold 7", 984, 1092, 2.0, estimated=True),
    *_fold("Galaxy Z Fold 7 (density 2.625)", 750, 832, 2.625, estimated=True),
    Device("Galaxy Z Fold 8 cover", Viewport(475, 751, 2.625), estimated=True),
    *_fold("Galaxy Z Fold 8", 704, 933, 2.625, estimated=True),
    *_fold("Galaxy Z Fold 8 (narrow)", 616, 816, 3.0, estimated=True),
    Device("Surface Duo single", Viewport(540, 720, 2.5)),
    Device("Surface Duo single, landscape", Viewport(720, 540, 2.5)),
    Device("Surface Duo spanned", Viewport(1114, 720, 2.5, hinge=(540, 34))),
    *_tablet("Galaxy Tab S8 / S9", 800, 1280, estimated=True),
    *_tablet("Galaxy Tab S8+ / S9+ / S10+", 876, 1400, estimated=True),
    *_tablet("Galaxy Tab S8 / S9 / S10 Ultra", 924, 1480, estimated=True),
    *_tablet("iPad mini", 744, 1133),
    *_tablet("iPad mini (DevTools preset)", 768, 1024),
    *_tablet("iPad (9th gen)", 810, 1080),
    *_tablet("iPad Pro 13 inch", 1032, 1376),
]


def apply_viewport(driver: WebDriver, viewport: Viewport, dpr: float | None = None) -> None:
    """Emulate `viewport` after navigation (chromedriver resets emulation per page load)."""
    metrics: dict[str, object] = {
        "width": viewport.width,
        "height": viewport.height,
        "deviceScaleFactor": dpr if dpr is not None else viewport.dpr,
        "mobile": True,
    }
    if viewport.hinge is not None:
        x, width = viewport.hinge
        metrics["displayFeature"] = {"orientation": "vertical", "offset": x, "maskLength": width}
    driver.execute_cdp_cmd("Emulation.setDeviceMetricsOverride", metrics)
