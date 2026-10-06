from __future__ import annotations

import pytest
from lxml import etree

from deckforge.template.ooxml import NS, ColorResolver, apply_transforms, emu_to_in

A = NS["a"]


def _el(xml: str) -> etree._Element:
    return etree.fromstring(f'<root xmlns:a="{A}">{xml}</root>')[0]


def test_emu_to_in() -> None:
    assert emu_to_in(914_400) == 1.0
    assert emu_to_in(None) == 0.0


@pytest.mark.parametrize(
    ("xml", "expected"),
    [
        ('<a:srgbClr val="808080"/>', "808080"),
        ('<a:srgbClr val="FFFFFF"><a:lumMod val="50000"/></a:srgbClr>', "808080"),
        ('<a:srgbClr val="000000"><a:lumOff val="100000"/></a:srgbClr>', "FFFFFF"),
        ('<a:srgbClr val="FF0000"><a:shade val="50000"/></a:srgbClr>', "800000"),
        ('<a:srgbClr val="000000"><a:tint val="0"/></a:srgbClr>', "FFFFFF"),
    ],
)
def test_apply_transforms(xml: str, expected: str) -> None:
    el = _el(xml)
    assert apply_transforms(el.get("val"), el) == expected


def test_resolver_maps_scheme_through_clr_map() -> None:
    r = ColorResolver({"dk1": "000000", "lt1": "FFFFFF", "accent1": "113D63"}, {"tx1": "lt1"})
    assert r.resolve(_el('<a:schemeClr val="tx1"/>')) == "FFFFFF"
    assert r.resolve(_el('<a:schemeClr val="accent1"/>')) == "113D63"
    assert r.resolve(_el('<a:sysClr val="windowText" lastClr="000000"/>')) == "000000"
    assert r.resolve(_el('<a:schemeClr val="missing"/>')) is None
    assert r.resolve(None) is None
