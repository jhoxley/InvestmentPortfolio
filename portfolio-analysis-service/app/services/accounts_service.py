"""Service providing account existence and per-resource date-range lookups.

Shared by the main time series endpoint (account validation and default-date-range
resolution) and the accounts-enumeration endpoint.
"""

from app.models.timeseries import AccountResourceRange, AccountSummary
from app.repositories.capital_repository import CapitalRepository
from app.repositories.ladder_repository import LadderRepository


class AccountsService:
    """Looks up which accounts are known and each resource's date range."""

    def __init__(self, ladder_repo: LadderRepository, capital_repo: CapitalRepository) -> None:
        """Initialise with the two underlying repositories.

        Args:
            ladder_repo: Repository for position ladders.
            capital_repo: Repository for capital ledgers.
        """
        self._ladder_repo = ladder_repo
        self._capital_repo = capital_repo

    def list_known_accounts(self) -> list[str]:
        """Return every account name known to either repository, sorted.

        Returns:
            Sorted, deduplicated union of both repositories' account names.
        """
        names = set(self._ladder_repo.list_accounts()) | set(self._capital_repo.list_accounts())
        return sorted(names)

    def get_summary(self, account_name: str) -> AccountSummary:
        """Build the per-resource date-range summary for one account.

        Args:
            account_name: The account identifier.

        Returns:
            AccountSummary with capital_ledger/position_ladder set to None for
            whichever resource has not been ingested for this account.
        """
        capital_ledger = None
        if self._capital_repo.exists(account_name):
            capital_meta = self._capital_repo.read_meta(account_name)
            capital_ledger = AccountResourceRange(
                from_date=capital_meta.from_date, to_date=capital_meta.to_date
            )

        position_ladder = None
        if self._ladder_repo.exists(account_name):
            ladder_meta = self._ladder_repo.read_meta(account_name)
            position_ladder = AccountResourceRange(
                from_date=ladder_meta.from_date, to_date=ladder_meta.to_date
            )

        return AccountSummary(
            account_name=account_name,
            capital_ledger=capital_ledger,
            position_ladder=position_ladder,
        )

    def list_summaries(self) -> list[AccountSummary]:
        """Build a summary for every known account.

        Returns:
            One AccountSummary per account returned by list_known_accounts().
        """
        return [self.get_summary(name) for name in self.list_known_accounts()]
