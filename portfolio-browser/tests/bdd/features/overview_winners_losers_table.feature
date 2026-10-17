Feature: Overview biggest winners and losers table
  As a user of the Investment Portfolio Browser
  I want a compact table of the biggest winners and losers on the Overview page
  So that I can see what's driving my results without scanning every position (FR-005-FR-009, FR-013)

  Background:
    Given portfolio-analysis-service has an account with position data

  Scenario: The table is captioned "Biggest winners and losers"
    Given the Overview page has finished loading its default chart
    Then a table captioned "Biggest winners and losers" is shown to the right of the pie chart

  Scenario: With 10 or more qualifying positions, the table shows the top 5 and bottom 5 by profit/loss
    Given portfolio-analysis-service has an account with 12 positions with recorded profit/loss
    Given the Overview page has finished loading its default chart
    Then the first 5 rows are the 5 highest profit/loss positions in descending order
    And the last 5 rows are the 5 lowest profit/loss positions, mildest first and worst last
    And no position appears twice in the table

  Scenario: Row backgrounds shade from bright green through pale green, then pale blue through bright blue
    Given portfolio-analysis-service has an account with 12 positions with recorded profit/loss
    Given the Overview page has finished loading its default chart
    Then row 1 is shaded the brightest green and row 5 the palest green
    And row 6 is shaded the palest blue and row 10 the brightest blue

  Scenario: Each row shows the position name, profit/loss, and book cost
    Given the Overview page has finished loading its default chart
    Then each row of the winners/losers table shows a position name, its profit/loss, and its book cost

  Scenario: Fewer than 10 qualifying positions shows every one exactly once
    Given portfolio-analysis-service has an account with 6 positions with recorded profit/loss
    Given the Overview page has finished loading its default chart
    Then the winners/losers table shows exactly 6 rows with no position repeated

  Scenario: Changing the account or "To" date refreshes the table
    Given the Overview page has finished loading its default chart
    When the user selects a different account
    Then the winners/losers table refreshes to that account's own biggest winners and losers
