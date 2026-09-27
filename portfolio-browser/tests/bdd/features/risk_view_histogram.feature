Feature: Return distribution on the Risk page
  As a user of the Investment Portfolio Browser
  I want the Risk page to show a return histogram and its statistics immediately
  So that I understand an account's volatility at a glance with no setup (User Story 1)

  Background:
    Given portfolio-analysis-service has multiple accounts with recorded return history

  Scenario: The Risk page exists and is reachable from navigation
    When the browser loads the Risk page and its content finishes loading
    Then the sidebar shows a "Risk" navigation entry

  Scenario: Opening the page shows a histogram and a statistics table
    When the browser loads the Risk page and its content finishes loading
    Then a bar chart is displayed with basis-point buckets on the X-axis
    And a statistics table is displayed with columns headed "statistic" and "value"
    And the table's rows are exactly count, mean, median, mode, minimum, maximum, std_dev, skewness, kurtosis in that order
    And the table has no "std_dev_bands" row

  Scenario: The chart and table sit side by side in a single row
    When the browser loads the Risk page and its content finishes loading
    Then the bar chart and the statistics table appear in the same row
    And the bar chart occupies the majority of that row's width

  Scenario: An account with no observations in range shows a clear message
    Given portfolio-analysis-service has an account with no recorded return observations
    When the browser loads the Risk page and its content finishes loading
    Then a "no data" message is shown instead of a chart or table

  Scenario: A failure looking up accounts shows an error state
    Given portfolio-analysis-service is unavailable for account lookups
    When the browser loads the Risk page and its content finishes loading
    Then an error-state message is shown instead of a chart or an indefinite loading spinner

  Scenario: A failure fetching the histogram shows an error state
    Given portfolio-analysis-service is unavailable for return histogram data
    When the browser loads the Risk page and its content finishes loading
    Then an error-state message is shown instead of a chart or an indefinite loading spinner
