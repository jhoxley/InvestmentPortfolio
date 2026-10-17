Feature: Portfolio daily return histogram

  @us1
  Scenario: Daily returns are bucketed by rounded basis points
    Given account "hist-acct" has daily portfolio returns of 0.0010, 0.00104, 0.0011, -0.0025 and 0.0010 on consecutive business days from 2024-01-02
    When the return histogram is requested from 2024-01-02 to 2024-01-08
    Then the histogram response status is 200
    And the histogram buckets are "-25:1, 10:3, 11:1"

  @us1
  Scenario: Buckets with no observations are omitted
    Given account "hist-acct" has daily portfolio returns of -0.0005 and 0.0005 on consecutive business days from 2024-01-02
    When the return histogram is requested from 2024-01-02 to 2024-01-03
    Then the histogram response status is 200
    And the histogram buckets are "-5:1, 5:1"

  @us1
  Scenario: Buckets are sorted from smallest to largest
    Given account "hist-acct" has daily portfolio returns of 0.0012, -0.0003, 0.0 and 0.0007 on consecutive business days from 2024-01-02
    When the return histogram is requested from 2024-01-02 to 2024-01-05
    Then the histogram response status is 200
    And the histogram buckets are "-3:1, 0:1, 7:1, 12:1"

  @us1
  Scenario: Portfolio-level daily return is the sum of weighted position returns
    Given account "hist-acct" has sub-accounts "Equities A" and "Equities B" with weighted position returns 0.011 and -0.0045 on 2024-03-04
    When the return histogram is requested from 2024-03-04 to 2024-03-04
    Then the histogram response status is 200
    And the histogram buckets are "65:1"

  @us2
  Scenario: Statistics describe the same observations as the histogram
    Given account "hist-acct" has daily portfolio returns of -0.0010, 0.0, 0.0, 0.0010 and 0.0020 on consecutive business days from 2024-01-02
    When the return histogram is requested from 2024-01-02 to 2024-01-08
    Then the histogram response status is 200
    And the statistics report count 5, minimum -10, maximum 20, mean 4, median 0 and mode 0
    And each standard deviation band has a multiple equal to sigma times the standard deviation and edges at the mean minus and plus that multiple

  @us2
  Scenario: Statistics count matches the histogram
    Given account "hist-acct" has daily portfolio returns of 0.0010, 0.00104, 0.0011, -0.0025 and 0.0010 on consecutive business days from 2024-01-02
    When the return histogram is requested from 2024-01-02 to 2024-01-08
    Then the histogram response status is 200
    And the statistics count equals the sum of all histogram bucket counts

  @us3
  Scenario: Histogram and performance use the same daily returns
    Given account "hist-acct" has daily portfolio returns of 0.0010, 0.0020, 0.0, -0.0010, 0.0005, 0.0030, 0.0 and 0.0010 on consecutive business days from 2024-01-02
    When the return histogram is requested from 2024-01-02 to 2024-01-11
    And the performance endpoint is requested for attribute "ITD" from 2024-01-02 to 2024-01-11
    Then the histogram statistics count equals the number of performance entries
    And the histogram and performance responses have the same from_date and to_date

  @us3
  Scenario: Default start and end resolve like the performance endpoint
    Given account "hist-acct" has daily portfolio returns of 0.0010, 0.0020 and 0.0030 on consecutive business days from 2024-01-02
    When the return histogram is requested with no start or end date
    And the performance endpoint is requested for attribute "ITD" with no start or end date
    Then the histogram response status is 200
    And the histogram and performance responses have the same from_date and to_date
    And the histogram statistics count equals the number of performance entries

  @us4
  Scenario: Start date after end date is rejected
    Given account "hist-acct" has daily portfolio returns of 0.0010, 0.0020 and 0.0030 on consecutive business days from 2024-01-02
    When the return histogram is requested from 2024-06-03 to 2024-01-03
    Then the histogram response status is 422
    And the histogram response is a problem details document

  @us4
  Scenario: Unknown account is reported as not found
    Given no account named "missing-acct" exists
    When the return histogram is requested from 2024-01-02 to 2024-01-03
    Then the histogram response status is 404
    And the histogram response is a problem details document

  @us4
  Scenario: Invalid account name is rejected
    Given no account named "bad name!" exists
    When the return histogram is requested from 2024-01-02 to 2024-01-03
    Then the histogram response status is 422
    And the histogram response is a problem details document

  @us4
  Scenario: Future end date is rejected
    Given account "hist-acct" has daily portfolio returns of 0.0010, 0.0020 and 0.0030 on consecutive business days from 2024-01-02
    When the return histogram is requested from 2024-01-02 to 2999-01-01
    Then the histogram response status is 422
    And the histogram response is a problem details document

  @us4
  Scenario: Account without a position ladder is rejected
    Given account "cap-only" has only a capital ledger
    When the return histogram is requested from 2024-01-02 to 2024-01-03
    Then the histogram response status is 422
    And the histogram response is a problem details document

  @us4
  Scenario: Weekend end date follows performance date adjustment
    Given account "hist-acct" has daily portfolio returns of 0.0010, 0.0020, 0.0030, 0.0040, 0.0050 and 0.0060 on consecutive business days from 2024-01-02
    When the return histogram is requested from 2024-01-02 to 2024-01-06
    And the performance endpoint is requested for attribute "ITD" from 2024-01-02 to 2024-01-06
    Then the histogram response status is 200
    And the histogram to_date is 2024-01-08
    And the histogram and performance responses have the same from_date and to_date

  @us4
  Scenario: Single-day window
    Given account "hist-acct" has daily portfolio returns of 0.0010, 0.0020 and 0.0030 on consecutive business days from 2024-01-02
    When the return histogram is requested from 2024-01-03 to 2024-01-03
    Then the histogram response status is 200
    And the histogram buckets are "20:1"
    And the statistics have one observation with undefined standard deviation, skewness and kurtosis
