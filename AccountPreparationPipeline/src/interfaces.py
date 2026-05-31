from __future__ import annotations

from argparse import ArgumentParser, Namespace
from typing import Protocol, runtime_checkable

from src.context import ExecutionContext


@runtime_checkable
class ModeInterface(Protocol):
    name: str
    description: str

    def register_arguments(self, parser: ArgumentParser) -> None: ...

    def execute(self, context: ExecutionContext, args: Namespace) -> int: ...
