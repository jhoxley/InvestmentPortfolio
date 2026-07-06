Feature: Discover available modes and mode-specific arguments
  As a developer
  I want to discover what the pipeline can do and how to use each mode
  So that I can operate the pipeline without reading source code

  # US2: Top-level help
  Scenario: Invoking with no arguments shows top-level help
    Given the pipeline entrypoint exists
    When I invoke the pipeline with no arguments
    Then the exit code is 0
    And the output contains the word "example"
    And the output contains a mode description

  Scenario: Invoking with --help shows top-level help
    Given the pipeline entrypoint exists
    When I invoke the pipeline with arguments "--help"
    Then the exit code is 0
    And the output contains the word "example"

  Scenario: Top-level help lists every registered mode
    Given the pipeline entrypoint exists
    When I invoke the pipeline with arguments "--help"
    Then the exit code is 0
    And the output contains the word "example"

  # US3: Mode-level help
  Scenario: Invoking a mode with --help shows mode argument list
    Given the pipeline entrypoint exists
    When I invoke the pipeline with arguments "example --help"
    Then the exit code is 0
    And the output contains the argument name "--message"
    And the output contains a description for the argument

  Scenario: Mode help shows required status for each argument
    Given the pipeline entrypoint exists
    When I invoke the pipeline with arguments "example --help"
    Then the exit code is 0
    And the output contains the argument name "--message"
