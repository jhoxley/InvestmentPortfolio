Feature: Run a supported pipeline mode
  As a developer
  I want to execute a named pipeline mode with valid arguments
  So that the mode logic runs and produces structured logs and a metrics summary

  Scenario: Valid mode with valid arguments exits successfully
    Given the pipeline entrypoint exists
    When I invoke the pipeline with arguments "example --message hello"
    Then the exit code is 0
    And the log output contains a JSON log entry
    And the log output contains a metrics record

  Scenario: Valid mode with missing required argument exits with error
    Given the pipeline entrypoint exists
    When I invoke the pipeline with arguments "example"
    Then the exit code is not 0
    And the error output mentions the missing argument

  Scenario: Valid mode with unrecognised argument exits with error
    Given the pipeline entrypoint exists
    When I invoke the pipeline with arguments "example --message hello --bogus value"
    Then the exit code is not 0
