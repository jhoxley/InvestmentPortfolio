Feature: View build/version information in the footer
  As a user of the Investment Portfolio Browser
  I want to see the software version and last-published date in the footer
  So that I can confirm which build I'm using

  Background:
    Given the app is launched

  Scenario: Footer shows version and published date on load
    When the browser loads the page
    Then a footer is visible showing a software version and a last-published date

  Scenario: Footer content is unchanged after navigating to another section
    Given the app is loaded with "Overview" selected by default
    When the user clicks the "Positions" navigation item
    Then a footer is visible showing a software version and a last-published date
