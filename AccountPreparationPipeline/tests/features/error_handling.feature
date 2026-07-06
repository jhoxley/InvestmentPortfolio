Feature: Handle invalid invocations gracefully
  As a developer
  I want clear error messages when I misuse the pipeline
  So that I can quickly understand and correct my mistake without reading a stack trace

  Scenario: Unrecognised mode exits with error and lists valid modes
    Given the pipeline entrypoint exists
    When I invoke the pipeline with arguments "nonexistentmode"
    Then the exit code is not 0
    And the error output mentions the unknown mode name
    And the error output lists the valid modes
    And the error output contains no traceback

  Scenario: Unrecognised mode exit code is 1
    Given the pipeline entrypoint exists
    When I invoke the pipeline with arguments "badmode"
    Then the exit code is 1
