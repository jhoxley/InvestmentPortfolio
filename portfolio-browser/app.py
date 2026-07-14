"""Entrypoint: builds the Dash app shell and runs the dev server."""

from __future__ import annotations

from pathlib import Path

import dash_bootstrap_components as dbc
from dash import Dash

from config.content import load_content_config
from config.settings import Settings
from src.layout.shell import build_shell

_ROOT = Path(__file__).resolve().parent
_CONTENT_PATH = _ROOT / "config" / "content.yaml"
_PAGES_FOLDER = _ROOT / "src" / "pages"


def create_app() -> Dash:
    content = load_content_config(_CONTENT_PATH)
    app = Dash(
        __name__,
        use_pages=True,
        pages_folder=str(_PAGES_FOLDER),
        external_stylesheets=[dbc.themes.BOOTSTRAP],
        title=content.app_name,
    )
    app.layout = build_shell(content)
    return app


app = create_app()
server = app.server

if __name__ == "__main__":
    settings = Settings()
    app.run(host=settings.host, port=settings.port, debug=settings.debug)
