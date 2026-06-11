from __future__ import annotations

import logging
from typing import Any

import pandas as pd

_logger = logging.getLogger("pipeline.modes.create_ledger.transaction_id")


def _normalise_date(val: Any) -> str:
    return str(pd.Timestamp(val).date())


class TransactionIDAssigner:
    def assign(
        self,
        df: pd.DataFrame,
        prior_ids: dict[tuple[str, str, str, str], str],
    ) -> pd.Series[str]:
        if df.empty:
            return pd.Series([], dtype=str, index=df.index)

        keys = [
            (_normalise_date(row.date), row.account, row.sub_account, row.reference)
            for _, row in df.iterrows()
        ]

        has_existing = any(k in prior_ids for k in keys)

        if not has_existing:
            result_list = [f"{i + 1:05d}-001" for i in range(len(df))]
            _logger.debug(
                "Transaction IDs assigned",
                extra={"count": len(df), "mode": "first_time"},
            )
            return pd.Series(result_list, index=df.index, dtype=str)

        # Re-run: build max suffix tracker from all prior IDs
        max_suffix_by_prefix: dict[int, int] = {}
        for tid in prior_ids.values():
            p, s = self._parse_id(tid)
            if p not in max_suffix_by_prefix or s > max_suffix_by_prefix[p]:
                max_suffix_by_prefix[p] = s

        max_prior_prefix = max(max_suffix_by_prefix.keys(), default=0)
        next_new_prefix = max_prior_prefix + 1

        result_list2: list[str | None] = [None] * len(df)

        for i, key in enumerate(keys):
            if key in prior_ids:
                result_list2[i] = prior_ids[key]
            else:
                is_insertion = any(keys[j] in prior_ids for j in range(i + 1, len(keys)))

                if is_insertion:
                    preceding_tid: str | None = None
                    for j in range(i - 1, -1, -1):
                        if result_list2[j] is not None:
                            preceding_tid = result_list2[j]
                            break

                    if preceding_tid is not None:
                        p, _ = self._parse_id(preceding_tid)
                        new_s = max_suffix_by_prefix.get(p, 0) + 1
                        max_suffix_by_prefix[p] = new_s
                        result_list2[i] = f"{p:05d}-{new_s:03d}"
                    else:
                        result_list2[i] = f"{next_new_prefix:05d}-001"
                        max_suffix_by_prefix[next_new_prefix] = 1
                        next_new_prefix += 1
                else:
                    result_list2[i] = f"{next_new_prefix:05d}-001"
                    max_suffix_by_prefix[next_new_prefix] = 1
                    next_new_prefix += 1

        _logger.debug(
            "Transaction IDs assigned",
            extra={"count": len(df), "mode": "re_run"},
        )
        return pd.Series(result_list2, index=df.index, dtype=str)

    def _parse_id(self, tid: str) -> tuple[int, int]:
        prefix_str, suffix_str = tid.split("-")
        return int(prefix_str), int(suffix_str)
