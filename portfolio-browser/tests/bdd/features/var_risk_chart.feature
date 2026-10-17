Feature: Value at Risk main chart
  As a user of the Investment Portfolio Browser
  I want to see each day's realised PnL next to the VaR forecast that applied to it
  So that I can judge whether the risk model has kept pace with what actually happened (User Story 1)

  Background:
    Given portfolio-analysis-service has an account with a completed VaR calculation

  Scenario: Opening the tab shows realised PnL bars with a VaR overlay
    Given the browser has loaded the Risk page and its content finished loading
    When the Value at Risk section finishes loading
    Then the chart, the linked market-value chart and the backtest panel are all present

  Scenario: A day whose loss exceeded its forecast is visually distinguished
    Given portfolio-analysis-service has a VaR series with an exceedance day
    And the browser has loaded the Risk page and its content finished loading
    When the Value at Risk section finishes loading
    Then the exceedance day's bar is coloured differently from non-exceeding days

  Scenario: Expected Shortfall can optionally be shown
    Given the browser has loaded the Risk page and its content finished loading
    When the Value at Risk section finishes loading
    And I turn on the Expected Shortfall display
    Then a dashed Expected Shortfall overlay line appears on the chart

  Scenario: The legend no longer overlaps the backtest summary panel
    Given the browser has loaded the Risk page and its content finished loading
    When the Value at Risk section finishes loading
    Then the chart's legend renders below the chart's plotting area
    And the backtest summary panel is fully visible within the viewport

  Scenario: Switching to percentage units hides the realised PnL bars, not the forecast line
    Given the browser has loaded the Risk page and its content finished loading
    When the Value at Risk section finishes loading
    And I switch units to percentage
    Then no realised PnL bars are shown on the chart
    And the VaR forecast line is still shown on the chart
    When I switch units to money
    Then the realised PnL bars reappear on the chart

  Scenario: Each chart section has a caption explaining what it shows
    Given the browser has loaded the Risk page and its content finished loading
    When the Value at Risk section finishes loading
    Then a caption is visible above the main chart
    And a different caption is visible above the linked market-value chart
