Feature: Non-Overview/Positions routes keep the unchanged 015 placeholder parameters bar
  As a user of the Investment Portfolio Browser
  I want the Performance/Income sections to look exactly as before
  So that the 016 Overview feature and the 018 Positions feature do not
  regress the rest of the shell (FR-007)

  Scenario Outline: The static, disabled placeholder bar is unchanged on non-Overview/Positions routes
    Given the app is launched
    When the user clicks the "<section>" navigation item
    Then the parameters bar shows the static, disabled Account and Date range placeholder controls
    And no metric-toggle panel is shown

    Examples:
      | section     |
      | Performance |
      | Income      |

  Scenario: The Overview route shows real controls, not the static placeholder
    When the browser loads the Overview page
    Then the parameters bar shows real, enabled Account and date-range controls

  Scenario: The Positions route shows real controls, not the static placeholder
    When the browser loads the Positions page
    Then the parameters bar shows real, enabled Account and date-range controls
