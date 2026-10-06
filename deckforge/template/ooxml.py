"""Low-level OOXML helpers: namespaces, XPath, units, and color resolution."""

from __future__ import annotations

import colorsys
from collections.abc import Mapping
from functools import lru_cache
from typing import Any

from lxml import etree

NS: dict[str, str] = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "c": "http://schemas.openxmlformats.org/drawingml/2006/chart",
}

EMU_PER_INCH = 914_400
DEFAULT_FONT_SIZE_PT = 18.0  # OOXML default when no level in the chain sets `sz`

# Default master color map (used when a master omits <p:clrMap>).
DEFAULT_CLR_MAP: dict[str, str] = {
    "bg1": "lt1",
    "tx1": "dk1",
    "bg2": "lt2",
    "tx2": "dk2",
}

Element = Any  # lxml element; lxml ships no type stubs


@lru_cache(maxsize=256)
def _compiled(expr: str) -> etree.XPath:
    return etree.XPath(expr, namespaces=NS)


def xpath(el: Element, expr: str) -> list[Element]:
    """Evaluate a namespaced XPath that returns elements."""
    result = _compiled(expr)(el)
    return list(result) if isinstance(result, list) else []


def first(el: Element | None, expr: str) -> Element | None:
    if el is None:
        return None
    found = xpath(el, expr)
    return found[0] if found else None


def emu_to_in(value: int | None) -> float:
    return round((value or 0) / EMU_PER_INCH, 3)


def _clamp(v: float) -> float:
    return min(1.0, max(0.0, v))


def _hex_to_rgb(hex_: str) -> tuple[float, float, float]:
    return (int(hex_[0:2], 16) / 255, int(hex_[2:4], 16) / 255, int(hex_[4:6], 16) / 255)


def _rgb_to_hex(r: float, g: float, b: float) -> str:
    return "".join(f"{round(_clamp(c) * 255):02X}" for c in (r, g, b))


def apply_transforms(hex_: str, color_el: Element) -> str:
    """Apply DrawingML color transforms (lumMod/lumOff/tint/shade) to a base hex color."""
    r, g, b = _hex_to_rgb(hex_)
    for child in color_el:
        tag = etree.QName(child).localname
        val = int(child.get("val", "100000")) / 100_000
        if tag in ("lumMod", "lumOff"):
            h, lum, s = colorsys.rgb_to_hls(r, g, b)
            lum = lum * val if tag == "lumMod" else lum + val
            r, g, b = colorsys.hls_to_rgb(h, _clamp(lum), s)
        elif tag == "tint":
            r, g, b = (c + (1 - c) * (1 - val) for c in (r, g, b))
        elif tag == "shade":
            r, g, b = (c * val for c in (r, g, b))
    return _rgb_to_hex(r, g, b)


class ColorResolver:
    """Resolves DrawingML color elements to `RRGGBB` using a theme and master color map."""

    def __init__(self, theme_colors: Mapping[str, str], clr_map: Mapping[str, str]) -> None:
        self._theme = dict(theme_colors)
        self._map = {**DEFAULT_CLR_MAP, **clr_map}

    def scheme(self, slot: str) -> str | None:
        return self._theme.get(self._map.get(slot, slot))

    def resolve(self, color_el: Element | None) -> str | None:
        """Resolve a color choice element (srgbClr, schemeClr, sysClr, prstClr)."""
        if color_el is None:
            return None
        tag = etree.QName(color_el).localname
        base: str | None
        if tag == "srgbClr":
            base = color_el.get("val")
        elif tag == "schemeClr":
            base = self.scheme(color_el.get("val", ""))
        elif tag == "sysClr":
            base = color_el.get("lastClr")
        elif tag == "prstClr":
            base = _PRESET_COLORS.get(color_el.get("val", ""))
        else:
            return None
        return apply_transforms(base.upper(), color_el) if base else None

    def solid_fill(self, parent: Element | None) -> str | None:
        """Color of a `<a:solidFill>` directly under `parent`, if present."""
        fill = first(parent, "a:solidFill")
        return self.resolve(fill[0]) if fill is not None and len(fill) else None


_PRESET_COLORS = {"black": "000000", "white": "FFFFFF", "red": "FF0000", "blue": "0000FF"}
