# Research: Capital Ledger Mode

**Feature**: 011-capital-ledger-mode
**Date**: 2026-07-01

## Decision 1: Processing Order — Transaction ID vs Date Sort

**Decision**: Sort the input ledger by `Transaction ID` (ascending) before accumulating running
totals. Within a single date, rows are processed in the deterministic canonical order already
encoded in the Transaction ID (date, account, sub_account, reference ASC per spec 007).

**Rationale**: Using the Transaction ID column that already exists in the `create_ledger` output
is the natural canonical order. It ensures same-date rows (e.g. two buy trades on the same day)
are accumulated consistently and reproducibly. Sorting by `date` alone is non-deterministic for
same-day rows.

**Alternatives considered**: Sort by raw `(date, account, sub_account, reference)` directly.
Rejected because it duplicates the sort logic already encoded in the Transaction ID and could
diverge if `create_ledger`'s canonical order changes. Delegating to the existing Transaction ID
column respects the invariant from spec 007.

---

## Decision 2: Book Value Sign Convention

**Decision**: `book_value` is the cumulative net sum of `Transaction Value` from the input ledger
for `buy` and `sell` rows — using the already-sign-adjusted values from the ledger (not the raw
journal values). In the ledger, buy values are negated (outflow from Cash) and sell values remain
positive (inflow); the net reflects cost basis (negative = deployed capital).

**Rationale**: The `create_ledger` engine already sign-adjusts `Transaction Value` for buy/sell
rows via `adj_value = -value` for buy/sell. Reading `Transaction Value` from the ledger (not the
raw journal `value`) avoids reimplementing sign-adjustment logic and keeps the capital ledger
consistent with how the main ledger presents buy/sell values.

**Alternatives considered**: Re-read the raw journal and sign-adjust independently. Rejected —
would duplicate `create_ledger` logic and create a maintenance risk if sign conventions change.

---

## Decision 3: Forward-Fill Strategy

**Decision**: Use pandas `groupby`-style cumsum with `ffill` (forward-fill) per date group. After
computing per-date contribution totals for each column, perform a cumulative sum across dates.
Forward-fill ensures dates with zero contribution for a column carry the prior total.

**Rationale**: `pandas.DataFrame.fillna(method='ffill')` / `cumsum()` are idiomatic for this
pattern and well-tested. The combination of `groupby(date).sum()` → `cumsum()` followed by
`ffill()` for the date index produces the correct running total with carry-forward in a single
vectorised operation.

**Alternatives considered**: Row-by-row loop accumulation. Rejected — slower and harder to test;
the vectorised pandas approach is cleaner and consistent with how `LedgerEngine` handles cumulative
sums.

---

## Decision 4: Module Layout

**Decision**: Mirror the `create_ledger` module exactly:
- `src/modes/create_capital_ledger/constants.py` — named constants only
- `src/modes/create_capital_ledger/engine.py` — `CapitalLedgerEngine` with a single `run()` method
- `src/modes/create_capital_ledger/mode.py` — `CreateCapitalLedgerMode` with `register_arguments()`
  and `execute()`

**Rationale**: The `create_ledger` module is the direct predecessor for this feature; its
architecture is already constitution-compliant (SRP, type-annotated, no magic strings). Matching
its layout means no design novelty and a clear audit trail for reviewers.

**Alternatives considered**: Putting everything in a single file. Rejected per SRP — the
computational engine must be independently testable without a CLI context.

---

## Decision 5: run_pipeline.ps1 Capital Account Selection

**Decision**: Add a `IsCapitalAccount` boolean key to each account hashtable in `run_pipeline.ps1`
and a `CapitalLedgerPath` key to the two capital account hashtables. Step 3 is guarded by
`$account.IsCapitalAccount -eq $true`.

**Rationale**: Explicit opt-in is safer than inferring from the account `Name` string (e.g.
checking whether "Income" appears in the name). A boolean flag is unambiguous and readable.

**Alternatives considered**: Infer capital vs income from the `Name` field. Rejected because
string matching is fragile — if an account name changes, the guard silently breaks. Explicit opt-in
is declared intent.

**Capital account output paths**:
- HL SIPP: `$InvestmentsDir\HL_SIPP_Capital_Ledger.xlsx`
- HL ISA: `$InvestmentsDir\HL_ISA_Capital_Ledger.xlsx`
