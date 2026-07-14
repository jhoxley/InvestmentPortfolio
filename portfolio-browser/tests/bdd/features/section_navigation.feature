Feature: Navigate between placeholder sections
  As a user of the Investment Portfolio Browser
  I want clicking a nav item to update the content area without a full reload
  So that I can explore the different dashboard sections that later features will fill in

  Background:
    Given the app is launched

  Scenario Outline: Clicking a nav item updates the content area
    Given the app is loaded with "Overview" selected by default
    When the user clicks the "<section>" navigation item
    Then the main content area updates to show that section's placeholder content

    Examples:
      | section     |
      | Positions   |
      | Performance |
      | Income      |

  Scenario: Shell chrome persists across navigation
    Given the app is loaded with "Overview" selected by default
    When the user clicks the "Positions" navigation item
    Then the header, footer, and navigation menu remain visible and unchanged
