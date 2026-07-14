"""Step definitions for the application shell's BDD scenarios.

Shared across User Story 1 (application_shell.feature), User Story 2
(section_navigation.feature), and User Story 3 (build_info_footer.feature)
since all three drive the same running app instance via the `dash_duo`
browser fixture (see tasks.md's Dependencies section for why this file is
the one deliberate exception to "different files = parallelizable").
"""

from __future__ import annotations

from pytest_bdd import given, parsers, scenarios, then, when
from selenium.common.exceptions import StaleElementReferenceException

scenarios("../features/application_shell.feature")
scenarios("../features/section_navigation.feature")
scenarios("../features/build_info_footer.feature")

_SECTION_KEYS = {
    "Overview": "overview",
    "Positions": "positions",
    "Performance": "performance",
    "Income": "income",
}

_TABLET_WIDTH = 800
_DESKTOP_WIDTH = 1280
_VIEWPORT_HEIGHT = 900
_SIDEBAR_WIDTH_BUDGET = 0.20


@given("the app is launched", target_fixture="dash_app")
def the_app_is_launched(dash_duo):
    import app as app_module

    dash_duo.start_server(app_module.app)
    return app_module.app


@when("the browser loads the page")
def the_browser_loads_the_page(dash_duo, dash_app):
    dash_duo.wait_for_element("#app-header")


@then(parsers.parse('a header displaying "{text}" is visible at the top of the page'))
def header_is_visible(dash_duo, text):
    header = dash_duo.wait_for_element("#app-header")
    assert text in header.text


@when("the user views the page at a desktop viewport width")
def view_at_desktop_width(dash_duo):
    dash_duo.driver.set_window_size(_DESKTOP_WIDTH, _VIEWPORT_HEIGHT)
    dash_duo.wait_for_element("#app-sidebar")


@then("the left-hand navigation menu is visible")
def sidebar_is_visible(dash_duo):
    assert dash_duo.find_element("#app-sidebar").is_displayed()


@then("the navigation menu occupies no more than 20% of the page width")
def sidebar_width_within_budget(dash_duo):
    sidebar = dash_duo.find_element("#app-sidebar")
    viewport_width = dash_duo.driver.execute_script("return window.innerWidth")
    assert sidebar.size["width"] <= _SIDEBAR_WIDTH_BUDGET * viewport_width + 1


@when("the user views the main content area")
def view_the_main_content_area(dash_duo):
    dash_duo.wait_for_element("#app-content-frame")


@then("it occupies the remaining page width")
def content_frame_occupies_remaining_width(dash_duo):
    content_frame = dash_duo.find_element("#app-content-frame")
    sidebar = dash_duo.find_element("#app-sidebar")
    viewport_width = dash_duo.driver.execute_script("return window.innerWidth")
    assert content_frame.size["width"] >= viewport_width - sidebar.size["width"] - 20


@then("a parameters/controls placeholder section is positioned above the page content")
def parameters_bar_above_page_content(dash_duo):
    parameters_bar = dash_duo.find_element("#app-parameters-bar")
    page_content = dash_duo.find_element("#app-page-content")
    assert parameters_bar.location["y"] < page_content.location["y"]
    dash_duo.find_element("#app-parameters-account")
    dash_duo.find_element("#app-parameters-daterange")


@when("the user views the page at a tablet viewport width")
def view_at_tablet_width(dash_duo):
    dash_duo.driver.set_window_size(_TABLET_WIDTH, _VIEWPORT_HEIGHT)
    dash_duo.wait_for_element("#app-sidebar")


@then("the left-hand navigation menu is still visible")
def sidebar_still_visible(dash_duo):
    assert dash_duo.find_element("#app-sidebar").is_displayed()


@then("the navigation menu still occupies no more than 20% of the page width")
def sidebar_still_within_budget(dash_duo):
    sidebar_width_within_budget(dash_duo)


@then("the navigation menu does not overlap the content area")
def sidebar_does_not_overlap_content(dash_duo):
    sidebar = dash_duo.find_element("#app-sidebar")
    content_frame = dash_duo.find_element("#app-content-frame")
    assert sidebar.location["x"] + sidebar.size["width"] <= content_frame.location["x"] + 1


@then("the Overview section's placeholder content is shown without any navigation click")
def overview_shown_by_default(dash_duo):
    page_content = dash_duo.find_element("#app-page-content")
    assert "Overview placeholder" in page_content.text


@given('the app is loaded with "Overview" selected by default', target_fixture="shell_chrome")
def app_loaded_with_overview_default(dash_duo, dash_app):
    dash_duo.wait_for_element("#app-page-content")
    return {
        "header": dash_duo.find_element("#app-header"),
        "footer": dash_duo.find_element("#app-footer"),
        "sidebar": dash_duo.find_element("#app-sidebar"),
    }


@when(parsers.parse('the user clicks the "{section}" navigation item'))
def click_nav_item(dash_duo, section):
    key = _SECTION_KEYS[section]
    dash_duo.find_element(f"#app-sidebar-nav-{key}").click()
    dash_duo.wait_for_contains_text("#app-page-content", f"{section} placeholder")


@then("the main content area updates to show that section's placeholder content")
def content_area_updated(dash_duo):
    page_content = dash_duo.find_element("#app-page-content")
    assert any(
        f"{label} placeholder" in page_content.text
        for label in ("Positions", "Performance", "Income")
    )


@then("the header, footer, and navigation menu remain visible and unchanged")
def chrome_persists(shell_chrome):
    for name, element in shell_chrome.items():
        try:
            assert element.is_displayed(), f"{name} is no longer displayed"
        except StaleElementReferenceException:
            raise AssertionError(
                f"{name} was remounted (stale element) instead of persisting across navigation"
            ) from None


@then("a footer is visible showing a software version and a last-published date")
def footer_shows_build_info(dash_duo):
    footer = dash_duo.find_element("#app-footer")
    assert footer.is_displayed()
    assert "Version" in footer.text
    assert "Published" in footer.text
