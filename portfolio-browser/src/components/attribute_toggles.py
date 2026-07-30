"""Shared attribute-toggle control builder (Overview + Positions).

Extracted from `src/pages/overview.py`'s private `_attribute_toggle()` so
both pages present and behave identically for these controls, even though
each page's own attribute list comes from its own endpoint
(`/v1/timeseries/attributes` vs `/v1/positions/attributes`) — the shared
`AttributeDefinition` model already has the same shape either way
(specs/018-positions-page/research.md #2).
"""

from __future__ import annotations

import dash_bootstrap_components as dbc
from dash import html

from src.models.portfolio_analysis import AttributeDefinition


def build_attribute_toggle(
    attribute: AttributeDefinition, toggle_id_type: str, default_on: bool
) -> html.Div:
    """Build one attribute's toggle switch + tooltip.

    Args:
        attribute: The attribute this toggle represents.
        toggle_id_type: The pattern-matching `type` string the owning
            page's callback listens on (e.g. `"overview-attribute-toggle"`),
            also used as the DOM id prefix so each page's toggles remain
            uniquely identifiable.
        default_on: Whether this toggle starts switched on.

    Returns:
        An `html.Div` wrapping the `dbc.Switch` and its `dbc.Tooltip`.
    """
    toggle_id = {"type": toggle_id_type, "name": attribute.name}
    dom_id = f"{toggle_id_type}-{attribute.name}"
    # e.g. "overview-attribute-toggle" -> "overview-attribute-tooltip", matching
    # the DOM id convention already established (and BDD-tested) by Overview.
    tooltip_id = f"{toggle_id_type.replace('-toggle', '-tooltip')}-{attribute.name}"
    return html.Div(
        [
            dbc.Switch(
                id=toggle_id,
                label=attribute.name,
                value=default_on,
                className="d-inline-block me-2",
            ),
            dbc.Tooltip(
                attribute.description,
                target=dom_id,
                id=tooltip_id,
            ),
        ],
        id=dom_id,
        className="d-inline-block me-4",
    )


def build_attribute_toggles(
    attributes: list[AttributeDefinition],
    toggle_id_type: str,
    default_on_names: frozenset[str],
) -> list[html.Div]:
    """Build one toggle per attribute.

    Args:
        attributes: The full attribute list to render toggles for.
        toggle_id_type: See `build_attribute_toggle`.
        default_on_names: Attribute names that start switched on.

    Returns:
        A list of `html.Div` toggle components, in the same order as
        `attributes`.
    """
    return [
        build_attribute_toggle(attribute, toggle_id_type, attribute.name in default_on_names)
        for attribute in attributes
    ]
