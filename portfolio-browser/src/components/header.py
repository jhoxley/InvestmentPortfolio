"""Persistent header identifying the application (FR-001)."""

from __future__ import annotations

from dash import html

from config.content import ContentConfig


def build_header(content: ContentConfig) -> html.Header:
    return html.Header(
        html.H1(content.app_name, className="h4 m-0 py-2 px-3"),
        id="app-header",
        className="bg-primary text-white",
    )
