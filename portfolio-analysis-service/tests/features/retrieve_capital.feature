Feature: Retrieve Capital Ledger

  @us2
  Scenario: Retrieve summary of an existing capital ledger
    Given a capital ledger has previously been stored for account "test-portfolio"
    When a GET request is made for the capital ledger summary of "test-portfolio"
    Then the response status is 200
    And the response body is a JSON object containing row count and date range
    And the response body includes a "_links.self" and a "_links.download" URL

  @us2
  Scenario: Retrieve a capital ledger summary for an unknown account
    Given no capital ledger exists for account "unknown-account"
    When a GET request is made for the capital ledger summary of "unknown-account"
    Then the response status is 404
    And the response body contains a descriptive error message

  @us2
  Scenario: Download XLSX binary for a known account
    Given a capital ledger has previously been stored for account "download-portfolio"
    When a download request is made for the capital ledger of "download-portfolio"
    Then the download response status is 200
    And the content type is the XLSX MIME type
    And the Content-Disposition header specifies an attachment filename

  @us2
  Scenario: Download a capital ledger for an unknown account
    Given no capital ledger exists for account "unknown-account"
    When a download request is made for the capital ledger of "unknown-account"
    Then the download response status is 404
