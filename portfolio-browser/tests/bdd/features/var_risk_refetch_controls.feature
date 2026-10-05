Feature: Account, date and look-back changes refetch the Value at Risk tab
  As a user of the Investment Portfolio Browser
  I want to change account, dates or look-back using the same controls as elsewhere
  So that I can navigate the Value at Risk tab consistently with every other page (User Story 4)

  Background:
    Given portfolio-analysis-service has an account with a completed VaR calculation

  Scenario: Changing the account refetches the view
    Given the browser has loaded the Risk page and its content finished loading
    When I select the "Value at Risk" tab
    And I select a different account
    Then a new VaR series request was made for the newly selected account

  Scenario: Changing the date range refetches the view
    Given the browser has loaded the Risk page and its content finished loading
    When I select the "Value at Risk" tab
    And I change the date range
    Then a new VaR series request was made

  Scenario: Changing the look-back refetches the view
    Given the browser has loaded the Risk page and its content finished loading
    When I select the "Value at Risk" tab
    And I change the look-back to "1y"
    Then a new VaR series request was made with look-back "1y"
    And the chart no longer shows the previous selection's data

  Scenario: Periodicity controls have no effect on this view
    Given the browser has loaded the Risk page and its content finished loading
    When I select the "Value at Risk" tab
    Then no periodicity control is shown
