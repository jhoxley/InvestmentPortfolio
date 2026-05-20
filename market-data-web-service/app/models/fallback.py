from pathlib import Path

from pydantic import BaseModel, ConfigDict, field_validator


class FallbackEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    csv_path: Path
    currency: str
    date_column: str
    price_column: str
    use_local_only: bool = False

    @field_validator("currency")
    @classmethod
    def _validate_currency(cls, v: str) -> str:
        import re

        if not re.fullmatch(r"[A-Z]{3}", v):
            raise ValueError(f"currency must be a 3-letter ISO 4217 code, got '{v}'")
        return v
