Feature: Retrieve Position Ladder
  As a developer
  I want to retrieve a summary or download of a stored position ladder
  So that I can use it in downstream analysis

  @us2
  Scenario: Retrieve summary of an existing position ladder
    Given a position ladder has previously been stored for account "test-portfolio"
    When a GET request is made for the position ladder of "test-portfolio"
    Then the response status is 200
    And the response body is a JSON object containing row_count, from_date, to_date, and sub_accounts
    And the response body includes a "_links.self" and a "_links.download" URL

  @us2
  Scenario: Retrieve a ladder for an unknown account
    Given no position ladder exists for account "unknown-account"
    When a GET request is made for the position ladder of "unknown-account"
    Then the response status is 404
    And the response body contains a descriptive error message

  @us2
  Scenario: Download XLSX binary for a known account
    Given a position ladder has previously been stored for account "download-portfolio"
    When a download request is made for "download-portfolio"
    Then the download response status is 200
    And the content type is the XLSX MIME type
    And the Content-Disposition header specifies an attachment filename
