"""Left-hand navigation menu, ≤20% width, active-link state, scrollable overflow.

FR-003 (≤20% width), FR-007 (multi-section nav), FR-009 (shrink not collapse
at tablet width; nav list scrolls if it overflows viewport height).
"""

from __future__ import annotations

import dash_bootstrap_components as dbc

from config.content import ContentConfig, NavigationSection

_SIDEBAR_WIDTH = 2  # out of 12 grid columns (~16.7%), comfortably under the 20% budget
# at every Bootstrap breakpoint, since no responsive breakpoint override is applied.


def _href_for(section: NavigationSection, default_key: str) -> str:
    return "/" if section.key == default_key else f"/{section.key}"


def build_sidebar(content: ContentConfig) -> dbc.Col:
    default_key = content.default_section().key
    links = [
        dbc.NavLink(
            section.label,
            href=_href_for(section, default_key),
            id=f"app-sidebar-nav-{section.key}",
            active="exact",
        )
        for section in content.ordered_sections()
    ]
    nav = dbc.Nav(
        links,
        vertical=True,
        pills=True,
        id="app-sidebar-nav",
        style={"overflowY": "auto", "maxHeight": "calc(100vh - 8rem)"},
    )
    return dbc.Col(
        nav,
        id="app-sidebar",
        width=_SIDEBAR_WIDTH,
        className="bg-light border-end py-3",
    )
