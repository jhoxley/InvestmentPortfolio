from __future__ import annotations

from src.interfaces import ModeInterface


class ModeRegistry:
    def __init__(self) -> None:
        self._modes: dict[str, ModeInterface] = {}

    def register(self, mode: ModeInterface) -> None:
        if mode.name in self._modes:
            raise ValueError(f"Mode '{mode.name}' is already registered.")
        self._modes[mode.name] = mode

    def get(self, name: str) -> ModeInterface:
        if name not in self._modes:
            raise KeyError(f"Mode '{name}' is not registered.")
        return self._modes[name]

    def list_all(self) -> list[ModeInterface]:
        return sorted(self._modes.values(), key=lambda m: m.name)

    def contains(self, name: str) -> bool:
        return name in self._modes
