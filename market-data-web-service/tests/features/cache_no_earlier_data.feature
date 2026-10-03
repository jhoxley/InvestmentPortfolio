Feature: Remember that no history exists before an instrument's earliest observation

  Scenario: Empty earlier segment is fetched once and remembered
    Given a cache file exists for ticker "SHORT" covering 2024-01-02 to 2024-06-28
    And the data source has no observations before 2024-01-02
    When a consumer requests price history for "SHORT" from 2023-01-02 to 2024-06-28
    Then the response status code is 200
    And the data source was called for the earlier segment
    And the service has recorded that no data exists before 2024-01-02 for "SHORT"
    When the consumer repeats the request for "SHORT" from 2023-01-02 to 2024-06-28
    Then the data source was not called again for the earlier segment
    And both responses contain the same price entries

  Scenario: A request starting even earlier is also served without a data source call
    Given a cache file exists for ticker "SHORT" covering 2024-01-02 to 2024-06-28
    And the service has already recorded that no data exists before 2024-01-02 for "SHORT"
    When a consumer requests observed-only history for "SHORT" from 2020-01-02 to 2024-06-28
    Then the response status code is 200
    And the data source was not called for the earlier segment
    And the earliest price entry is 2024-01-02

  Scenario: Suppression of a known-empty segment is visible in the logs
    Given a cache file exists for ticker "SHORT" covering 2024-01-02 to 2024-06-28
    And the service has already recorded that no data exists before 2024-01-02 for "SHORT"
    When a consumer requests price history for "SHORT" from 2023-01-02 to 2024-06-28
    Then a log entry records that the earlier segment fetch was skipped for "SHORT" before 2024-01-02

  Scenario: Recording a newly discovered empty segment is visible in the logs
    Given a cache file exists for ticker "SHORT" covering 2024-01-02 to 2024-06-28
    And the data source has no observations before 2024-01-02
    When a consumer requests price history for "SHORT" from 2023-01-02 to 2024-06-28
    Then a log entry records that no earlier data exists for "SHORT" before 2024-01-02

  Scenario: Memory is invalidated when earlier data is later discovered
    Given a cache file exists for ticker "SHORT" covering 2024-01-02 to 2024-06-28
    And the service has already recorded that no data exists before 2024-01-02 for "SHORT"
    And the stored history for "SHORT" is cleared
    And the data source returns observations for "SHORT" starting 2023-03-01
    When a consumer requests observed-only history for "SHORT" from 2023-01-02 to 2024-06-28
    Then the response status code is 200
    And the earliest price entry is 2023-03-01
    And the recorded no-earlier-data boundary for "SHORT" is 2023-03-01

  Scenario: Remembered empty segment does not suppress fetching a later segment
    Given a cache file exists for ticker "SHORT" covering 2024-01-02 to 2024-06-28
    And the service has already recorded that no data exists before 2024-01-02 for "SHORT"
    And the data source returns observations for "SHORT" after 2024-06-28
    When a consumer requests price history for "SHORT" from 2023-01-02 to 2024-09-30
    Then the response status code is 200
    And the data source was called for the later segment
    And the data source was not called for the earlier segment

  Scenario: Boundary is recorded on the first request, before any history is stored
    Given no cache file exists for ticker "SHORT"
    And the data source returns observations for "SHORT" beginning 2024-01-02
    When a consumer requests price history for "SHORT" from 2023-01-02 to 2024-06-28
    Then the response status code is 200
    And the service has recorded that no data exists before 2024-01-02 for "SHORT"

  Scenario: A data source outage is never recorded as absence of data
    Given a cache file exists for ticker "SHORT" covering 2024-01-02 to 2024-06-28
    And the data source is unavailable
    When a consumer requests price history for "SHORT" from 2023-01-02 to 2024-06-28
    Then the response status code is 503
    And no no-earlier-data boundary is recorded for "SHORT"
