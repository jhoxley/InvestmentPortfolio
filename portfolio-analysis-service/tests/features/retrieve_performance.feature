Feature: Account Performance

  @us2
  Scenario: Requesting performance measures returns a timeseries-shaped response
    Given account "test-portfolio" has an ingested position ladder spanning 2020-01-02 through 2025-06-02
    When a performance request is made for attributes "ITD" and "1Y" from 2025-01-02 to 2025-01-10
    Then the response status is 200
    And the performance response has account_name "test-portfolio"
    And the performance response has attributes "ITD" and "1Y"
    And the performance response has from_date 2025-01-02 and to_date 2025-01-10
    And the performance response contains one entry per business day from 2025-01-02 to 2025-01-10
    And every performance entry contains a numeric "ITD" value and a numeric "1Y" value
    And the performance response body includes "_links.self", "_links.attributes", and "_links.accounts" URLs

  @us2
  Scenario: Same request arguments and defaults as the existing timeseries endpoint
    Given account "test-portfolio" has an ingested position ladder spanning 2020-01-02 through 2025-06-02
    When a performance request is made for attribute "ITD" with no start or end date
    Then the response status is 200
    And the performance response's from_date equals the ladder's earliest recorded date
    And the performance response's to_date is the business day before today

  @us2
  Scenario: All five performance measures populate for an account with more than 5 years of history
    Given account "test-portfolio" has an ingested position ladder spanning 2020-01-02 through 2025-06-02
    When a performance request is made for attributes "ITD", "ITD (Ann.)", "1Y", "3Y", and "5Y" on the account's most recent date
    Then the response status is 200
    And every one of "ITD", "ITD (Ann.)", "1Y", "3Y", and "5Y" is present and numeric on that entry

  @us1
  Scenario: Daily portfolio return is the sum of weighted position returns
    Given account "test-portfolio" has an ingested position ladder with two sub-accounts starting 2020-01-02
    When a performance request is made for attribute "ITD" for that account's first ingested date
    Then the response status is 200
    And the entry's "ITD" value equals the downloaded ladder's summed weighted_position_return for that date

  @us3
  Scenario: 3Y return for a narrow window still uses the full trailing history
    Given account "test-portfolio" has an ingested position ladder spanning 2020-01-02 through 2025-06-02
    When a performance request is made for attribute "3Y" with start 2023-06-01 and end 2023-06-01
    And a performance request is made for attribute "3Y" with start 2023-01-02 and end 2023-06-10
    Then both requests' "3Y" value for 2023-06-01 are equal

  @us3
  Scenario: Trailing return has no value before enough history exists
    Given account "test-portfolio" has an ingested position ladder spanning 2020-01-02 through 2025-06-02
    When a performance request is made for attribute "3Y" with start 2020-01-02 and end 2020-01-02
    Then the response status is 200
    And the single entry has no "3Y" key

  @us3
  Scenario: Short-tenure trailing measures are omitted together while inception measures still populate
    Given account "test-portfolio" has an ingested position ladder spanning 2020-01-02 through 2025-06-02
    When a performance request is made for attributes "ITD", "ITD (Ann.)", "1Y", "3Y", and "5Y" with start 2021-06-01 and end 2021-06-01
    Then the response status is 200
    And the single entry has numeric "ITD", "ITD (Ann.)", and "1Y" values
    And the single entry has neither a "3Y" nor a "5Y" key
