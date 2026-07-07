Feature: Configure Market Data Service Location and Identifier Mapping
  As an operator
  I want the market data service location and identifier mapping file path to be configurable
  So that I can deploy against different service instances and mapping files without code changes

  @us4
  Scenario: Market data service location is read from configuration
    Given portfolio-analysis-service is configured with an alternate market data service location
    When a ledger is ingested for an account requiring market data
    Then the price-history requests are sent to the configured location

  @us4
  Scenario: Identifier mapping file path is read from configuration
    Given portfolio-analysis-service is configured with an alternate identifier mapping source
    When a ledger is ingested
    Then the sub-account-to-identifier lookups use the configured mapping source

  @us4
  Scenario: End-to-end script wires the two services together
    Given the end-to-end run script defines market data service host and port variables
    Then the portfolio-analysis-service config block it writes uses those same variables
