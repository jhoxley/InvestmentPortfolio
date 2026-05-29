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

        # Allow major-unit codes (GBP, USD) and minor-unit codes (GBp, USd) — the third
        # char's case is the discriminator used by SubUnitNormaliser.
        if not re.fullmatch(r"[A-Za-z]{3}", v):
            raise ValueError(f"currency must be a 3-letter currency code, got '{v}'")
        return v
