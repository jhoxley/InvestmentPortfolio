"""Persistent footer showing Build Info (FR-002)."""

from __future__ import annotations

from dash import html

from config.content import ContentConfig


def build_footer(content: ContentConfig) -> html.Footer:
    build_info = content.build_info
    return html.Footer(
        html.Small(
            f"Version {build_info.version} · Published {build_info.published_date}",
            className="text-muted",
        ),
        id="app-footer",
        className="border-top py-2 px-3",
    )
