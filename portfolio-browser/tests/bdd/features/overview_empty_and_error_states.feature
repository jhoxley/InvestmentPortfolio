Feature: Overview chart empty and error states
  As a user of the Investment Portfolio Browser
  I want a clear message instead of a blank or broken chart
  So that I understand why no data is showing (FR-013, FR-014)

  Scenario: A valid selection with no data points shows an empty state
    Given portfolio-analysis-service has accounts and attributes but returns no data points for the default selection
    When the browser loads the Overview page
    Then an empty-state message is shown instead of a chart

  Scenario: A backing service failure shows an error state
    Given portfolio-analysis-service is unavailable
    When the browser loads the Overview page
    Then an error-state message is shown instead of a chart or an indefinite loading spinner

  Scenario: Turning off every metric toggle shows an empty state without a fetch
    Given the Overview page has finished loading its default chart
    When the user turns off every metric toggle
    Then an empty-state message is shown instead of a chart
