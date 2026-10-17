Feature: Persistent application shell
  As a user of the Investment Portfolio Browser
  I want a consistent header, navigation menu, and content frame
  So that future features have a stable place to live

  Background:
    Given the app is launched

  Scenario: Header identifies the application
    When the browser loads the page
    Then a header displaying "Investment Portfolio Browser" is visible at the top of the page

  Scenario: Sidebar occupies no more than 20% of the page width
    When the user views the page at a desktop viewport width
    Then the left-hand navigation menu is visible
    And the navigation menu occupies no more than 20% of the page width

  Scenario: Content area occupies the remaining width with a parameters bar above it
    When the user clicks the "Positions" navigation item
    And the user views the main content area
    Then it occupies the remaining page width
    And a parameters/controls placeholder section is positioned above the page content

  Scenario: Sidebar shrinks rather than collapses at a tablet viewport width
    When the user views the page at a tablet viewport width
    Then the left-hand navigation menu is still visible
    And the navigation menu still occupies no more than 20% of the page width
    And the navigation menu does not overlap the content area

  Scenario: Overview section is shown by default
    When the browser loads the page
    Then the Overview section's placeholder content is shown without any navigation click
