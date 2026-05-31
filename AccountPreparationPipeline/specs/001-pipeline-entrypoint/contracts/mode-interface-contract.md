# Contract: Mode Interface (Python Protocol)

**Feature**: 001-pipeline-entrypoint
**Date**: 2026-05-31
**Type**: Python structural interface contract

## Overview

Every mode module MUST satisfy this Protocol so the dispatcher can register and invoke it without
knowing its concrete type. The Protocol is defined using `typing.Protocol` (PEP 544) so no
inheritance is required — structural conformance is sufficient.

## Protocol Definition

```python
from argparse import ArgumentParser, Namespace
from typing import Protocol

class ModeInterface(Protocol):
    """Contract every pipeline mode module must satisfy."""

    name: str
    """Unique mode identifier; used as the CLI subcommand name.
    MUST be lowercase, hyphen-separated, no spaces."""

    description: str
    """One-line human-readable description shown in top-level --help.
    MUST be non-empty."""

    def register_arguments(self, parser: ArgumentParser) -> None:
        """Add the mode's accepted arguments to its argparse subparser.

        Called once at startup when the mode is registered.
        MUST NOT raise exceptions.
        """
        ...

    def execute(self, context: ExecutionContext, args: Namespace) -> int:
        """Execute the mode's logic.

        Args:
            context: The execution context for this pipeline run (correlation ID, start time, etc.)
            args:    The parsed argparse Namespace containing the mode's resolved arguments.

        Returns:
            Integer exit code. 0 = success. Non-zero = failure.

        Raises:
            Must NOT propagate unhandled exceptions — catch and return a non-zero exit code.
        """
        ...
```

## Rules for Mode Implementors

1. **`name`**: Class or module-level attribute. Lowercase, hyphen-separated. Must be unique across
   all registered modes (enforced by the registry at startup).

2. **`description`**: Class or module-level attribute. One sentence; no trailing period. Shown
   verbatim in `--help` output.

3. **`register_arguments(parser)`**: Called once at startup. Use `parser.add_argument(...)` to
   declare accepted arguments. Add `help=` strings for every argument — these appear in the
   mode's `--help` output (FR-006). Must not raise.

4. **`execute(context, args)`**: The mode's main logic. The `args` Namespace contains all
   arguments declared in `register_arguments`. Return `0` for success, non-zero for failure.
   Catch all exceptions internally — do not let them propagate to the dispatcher.

## Minimal Conforming Example

```python
from argparse import ArgumentParser, Namespace
from pipeline.context import ExecutionContext

class ExampleMode:
    name = "example"
    description = "A placeholder mode used for framework validation"

    def register_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--message",
            required=True,
            help="A message to echo back (validates argument passthrough).",
        )

    def execute(self, context: ExecutionContext, args: Namespace) -> int:
        # Real modes do actual work here.
        return 0
```

## Registration

Mode instances are registered with the `ModeRegistry` at application startup, before argument
parsing:

```python
registry.register(ExampleMode())
```

The registry validates that `name` is unique and that the object structurally conforms to
`ModeInterface` at registration time.
