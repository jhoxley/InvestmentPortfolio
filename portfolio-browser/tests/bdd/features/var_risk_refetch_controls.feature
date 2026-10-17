Feature: Account, date and range changes refetch the Value at Risk section
  As a user of the Investment Portfolio Browser
  I want to change account, dates or range using the same single set of controls as the histogram
  So that I never have to use a second, overlapping set of controls for this section (User Story 4; 027 User Story 3)

  Background:
    Given portfolio-analysis-service has an account with a completed VaR calculation

  Scenario: Changing the account refetches the view
    Given the browser has loaded the Risk page and its content finished loading
    When the Value at Risk section finishes loading
    And I select a different account
    Then a new VaR series request was made for the newly selected account

  Scenario: Changing the date range refetches the view
    Given the browser has loaded the Risk page and its content finished loading
    When the Value at Risk section finishes loading
    And I change the date range
    Then a new VaR series request was made

  Scenario: Clicking a shared shortcut button the Value at Risk section supports refetches it
    Given the browser has loaded the Risk page and its content finished loading
    When the Value at Risk section finishes loading
    And I click the "1Y" shortcut button
    Then a new VaR series request was made with look-back "1y"
    And the chart no longer shows the previous selection's data

  Scenario: Clicking a shared shortcut button the Value at Risk section cannot support shows its empty state
    Given the browser has loaded the Risk page and its content finished loading
    When the Value at Risk section finishes loading
    And I click the "3Y" shortcut button
    Then the histogram section still renders normally
    And the Value at Risk section shows "No Value at Risk data is available for the selected range"

  Scenario: There is no separate look-back control anywhere on the page
    Given the browser has loaded the Risk page and its content finished loading
    Then no "Look-back" control is shown in the Value at Risk section

  Scenario: Periodicity controls have no effect on this view
    Given the browser has loaded the Risk page and its content finished loading
    When the Value at Risk section finishes loading
    Then no periodicity control is shown
