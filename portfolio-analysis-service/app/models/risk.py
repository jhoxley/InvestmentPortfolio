"""Pydantic response models for the risk API."""

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class StdDevBand(BaseModel):
    """One standard deviation band around the mean, in basis points."""

    sigma: int = Field(description="Number of standard deviations: 1, 2 or 3")
    multiple: float = Field(description="sigma x sample standard deviation")
    lower: float = Field(description="mean minus multiple")
    upper: float = Field(description="mean plus multiple")


class HistogramStatistics(BaseModel):
    """Summary statistics of the rounded basis point observations.

    Values that are undefined for the available observations are None.
    """

    count: int = Field(description="Number of observations (business days)")
    mean: float | None = Field(description="Mean, in basis points")
    median: float | None = Field(description="Median, in basis points")
    mode: int | None = Field(description="Most frequent bucket (smallest on ties)")
    minimum: int | None = Field(description="Smallest bucket observed")
    maximum: int | None = Field(description="Largest bucket observed")
    std_dev: float | None = Field(
        description="Sample standard deviation in basis points; null when count < 2"
    )
    std_dev_bands: list[StdDevBand] = Field(
        description="Bands for sigma = 1, 2, 3; empty when std_dev is null"
    )
    skewness: float | None = Field(
        description="Sample skewness; null when count < 3 or std_dev is 0"
    )
    kurtosis: float | None = Field(
        description="Sample excess kurtosis; null when count < 4 or std_dev is 0"
    )


class ReturnHistogramResponse(BaseModel):
    """Response body for GET /v1/accounts/{account_name}/risk/return-histogram."""

    model_config = ConfigDict(populate_by_name=True)

    account_name: str = Field(description="Case-sensitive account identifier")
    from_date: date = Field(description="Resolved start date of the observation window")
    to_date: date = Field(description="Resolved end date of the observation window")
    histogram: list[tuple[int, int]] = Field(
        description=(
            "Pairs of [basis point bucket, number of business days in that bucket], sorted by "
            "bucket ascending; buckets with no observations are omitted"
        )
    )
    statistics: HistogramStatistics = Field(
        description="Distribution statistics over the same observations as the histogram"
    )
    links: dict[str, str] = Field(alias="_links", description="HATEOAS navigation links")
