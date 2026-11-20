# Responsive Device Viewport Matrix

CSS pixels (`width x height`) at the target device pixel ratio (DPR). This specification mirrors [`e2e/devices.py`](../e2e/devices.py) and drives automated layout assertions in [`e2e/test_device_matrix.py`](../e2e/test_device_matrix.py).

Two-pane [`SplitLayout`](../frontend/src/components/SplitLayout.vue) activates at `672px` (`--breakpoint-split: 42rem`) or whenever a vertical fold hinge (`horizontal-viewport-segments: 2`) is present. Navigation transitions to a vertical rail at `600px` (`--breakpoint-rail: 37.5rem`), while large-phone edge docks become available from `400px` (`--breakpoint-phone-lg: 25rem`).

- **Confirmed** viewports come from Chrome DevTools `EmulatedDevices` presets or manufacturer physical pixel / DPR specs.
- **Estimated** viewports are derived from third-party display specifications where no official DevTools preset exists yet.

| Device | Mode / Orientation | Viewport (CSS px) | DPR | Hinge `(x, width)` | Source |
|---|---|---|---|---|---|
| Galaxy Z Fold 4 | Cover | `344x882` | `2.625` | — | Confirmed (Fold 5 preset class) |
| Galaxy Z Fold 4 | Unfolded (flat & Flex hinge) | `690x829` | `2.625` | `(345, 0)` | Confirmed (Fold 5 preset class) |
| Galaxy Z Fold 5 | Cover | `344x882` | `2.625` | — | Confirmed (DevTools preset) |
| Galaxy Z Fold 5 | Unfolded (flat & Flex hinge) | `690x829` | `2.625` | `(345, 0)` | Confirmed (DevTools preset) |
| Galaxy Z Fold 6 | Cover | `412x968` | `2.625` | — | Confirmed (DevTools preset) |
| Galaxy Z Fold 6 | Unfolded (flat & Flex hinge) | `744x860` | `2.625` | `(372, 0)` | Confirmed (DevTools preset) |
| Galaxy Z Fold 7 | Cover | `411x960` | `2.625` | — | Estimated (`1080x2520 / 2.625`) |
| Galaxy Z Fold 7 | Unfolded (flat & Flex hinge) | `984x1092` | `2.0` | `(492, 0)` | Estimated (`1968x2184 / 2`) |
| Galaxy Z Fold 7 | Unfolded density `2.625` (flat & Flex) | `750x832` | `2.625` | `(375, 0)` | Estimated (`1968x2184 / 2.625`) |
| Galaxy Z Fold 8 | Cover | `475x751` | `2.625` | — | Estimated (panel spec) |
| Galaxy Z Fold 8 | Unfolded (flat & Flex hinge) | `704x933` | `2.625` | `(352, 0)` | Estimated (`1848x2448 / 2.625`) |
| Galaxy Z Fold 8 | Unfolded narrow (flat & Flex hinge) | `616x816` | `3.0` | `(308, 0)` | Estimated (`1848x2448 / 3`) |
| Surface Duo | Single screen (portrait / landscape) | `540x720` / `720x540` | `2.5` | — | Confirmed (DevTools preset) |
| Surface Duo | Spanned dual screen | `1114x720` | `2.5` | `(540, 34)` | Confirmed (DevTools vertical-spanned) |
| Galaxy Tab S8 / S9 | Portrait / Landscape | `800x1280` / `1280x800` | `2.0` | — | Estimated (`1600x2560 / 2`) |
| Galaxy Tab S8+ / S9+ / S10+ | Portrait / Landscape | `876x1400` / `1400x876` | `2.0` | — | Estimated (`1752x2800 / 2`) |
| Galaxy Tab S8 / S9 / S10 Ultra | Portrait / Landscape | `924x1480` / `1480x924` | `2.0` | — | Estimated (`1848x2960 / 2`) |
| iPad mini (6th / 7th gen) | Portrait / Landscape | `744x1133` / `1133x744` | `2.0` | — | Confirmed (`1488x2266 / 2`) |
| iPad mini (DevTools preset) | Portrait / Landscape | `768x1024` / `1024x768` | `2.0` | — | Confirmed (DevTools preset) |
| iPad (9th gen) | Portrait / Landscape | `810x1080` / `1080x810` | `2.0` | — | Confirmed (`1620x2160 / 2`) |
| iPad Pro 13" | Portrait / Landscape | `1032x1376` / `1376x1032` | `2.0` | — | Confirmed (DevTools preset) |

## Assertions Verified Per Viewport

For every unique viewport in [`DEVICES`](../e2e/devices.py) (36 device profiles grouped across cover, flat-unfolded, hinged Flex, spanned, portrait, and landscape views), `test_layout_holds_on_every_device` verifies:

1. **Zero horizontal overflow:** `scrollWidth <= window.innerWidth` on Home, Trip, Balances, and Settings views.
2. **Pane cardinality:** Two non-empty visible panes (`split-list` and `split-detail`) when `width >= 672` or a vertical hinge is active; one pane on narrow screens.
3. **Hinge clearance:** When a vertical hinge `(x, width)` is emulated via CDP `Emulation.setDeviceMetricsOverride`, `list_pane.right <= x` and `detail_pane.left >= x + width`, and `<nav>` never straddles the hinge gap.
4. **Rail non-overlap:** When `<nav>` docks as a vertical rail (`height > width`), it remains inside the viewport and never overlaps either content pane.
