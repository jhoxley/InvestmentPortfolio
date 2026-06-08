# Research: Trade Cash Offset Entries

**Feature**: 004-trade-cash-offsets
**Date**: 2026-06-05

## Decision 1: Placement of Offset Generation Logic

**Decision**: Introduce a dedicated `OffsetGenerator` class in a new file
`src/modes/consolidate_journals/offset_generator.py`. `ConsolidationEngine.run()` calls
`OffsetGenerator().generate(events)` after receiving parsed events from each fragment, then
passes the combined list (real events + offset events) to `JournalStore.merge()`.

**Rationale**:
- Single Responsibility Principle: offset generation is a distinct concern from fragment
  parsing and from journal storage/deduplication. Separating it into its own class keeps
  each module focused.
- The existing `ConsolidationEngine` orchestrates; it delegates all computation to helpers.
  Adding a helper is consistent with that pattern.
- `OffsetGenerator` has no I/O dependencies and can be unit-tested in complete isolation from
  the filesystem.

**Alternatives considered**:
- Embed offset generation directly in `ConsolidationEngine.run()`: Simpler but violates SRP
  and makes the engine harder to test independently. Rejected.
- Generate offsets in `JournalStore.merge()`: Would require the store to have knowledge of
  business rules (which actions generate offsets). Rejected — violates SRP more severely.
- Generate offsets as a post-processing step after `store.save()`: Would require a second
  read/write cycle. Rejected for being less efficient and more complex.

---

## Decision 2: Extension of ActionType Enum

**Decision**: Add `TRADING = "trading"` to the `ActionType` StrEnum in
`src/modes/consolidate_journals/schema.py`.

**Rationale**:
- The `action` field is typed as `ActionType` in `JournalEvent`. Offset rows carry
  `action = "trading"`. Using the enum keeps the type system consistent — no raw strings.
- Existing code paths (`_is_transaction_reference`, the HL parser) do not treat `trading`
  specially and will not be disrupted by the addition.
- `ActionType.TRADING` is never emitted by any fragment parser — it is exclusively produced
  by the offset generator — making the two concerns cleanly separated.

**Alternatives considered**:
- Use an existing action type (e.g., `DEPOSIT`): Would conflate real cash deposits with
  synthetic offset entries, making ledger analysis ambiguous. Rejected.
- Use a raw string `"trading"` without an enum value: Allows typos; violates the constitution's
  "no magic strings" rule. Rejected.

---

## Decision 3: Deduplication Strategy for Offset References

**Decision**: Add a new constant `RE_OFFSET: re.Pattern[str] = re.compile(r"^[BS]\d+-offset$")`
to `consolidate_journals/constants.py`. Extend `_is_transaction_reference()` in
`journal_store.py` to also return `True` when the reference matches `RE_OFFSET`. This ensures
offset references use the reliable `date + reference` dedup key rather than the fallback
`date + action + value` key.

**Rationale**:
- The existing fallback dedup key (`date + action + value`) would fail to distinguish two
  offset entries for buy/sell trades on the same date with identical values. The reference-based
  key (which includes the unique trade reference) is always correct for offset entries.
- Adding `RE_OFFSET` avoids changing `RE_BUY` and `RE_SELL`, which are also used by the HL
  parser for action mapping. Extending those regexes would incorrectly map an HL row whose
  reference is e.g. "B12345-offset" to `buy` action, which is undesirable.
- The pattern `^[BS]\d+-offset$` is specific enough to avoid false matches.

**Alternatives considered**:
- Extend `RE_BUY` and `RE_SELL` to `^B\d+(-offset)?$`: Simple, but risks corrupting the HL
  parser's action mapping if a real HL reference ever ends in `-offset`. Rejected.
- Use a string-suffix check (`reference.endswith("-offset")`): Would classify any reference
  ending in that suffix as a transaction reference, including non-trade offsets. Rejected as
  too broad.

---

## Decision 4: Offset Quantity = Negated Trade Value (not Negated Trade Quantity)

**Decision**: Each offset row's `quantity` field is set to `-event.value`, not `-event.quantity`.

**Rationale**:
- Spec FR-006 and Assumption 3 are explicit: the Cash position tracks money in/out, where
  `quantity` always equals `value`. Setting quantity to the negated value is consistent with
  how real Cash deposit/income rows are handled throughout the codebase.
- The trade event's own `quantity` represents units of the investment (e.g., number of fund
  units), which is meaningless in the Cash context.
- This matches how `create_ledger` subsequently processes Cash rows (FR-006 of feature 003).

**Alternatives considered**:
- Set `quantity = -event.quantity`: Would carry investment units into the Cash sub-account,
  making the Cash ledger entry nonsensical. Rejected.
- Set `quantity = None`: Would require special handling in `create_ledger` for Cash rows that
  already have a non-None quantity. Rejected.

---

## Decision 5: Offset Generation Scope — Full Backfill Pass (Updated after clarification)

**Decision**: After all fragment files are parsed and the journal is saved, run a backfill
pass: call `JournalStore.missing_offset_trades()` to find any buy/sell rows without a
corresponding offset, generate offsets for them via `OffsetGenerator`, merge them, and save
again (only if missing offsets exist). This replaces the original per-file approach.

**Rationale**:
- Clarification session (2026-06-08) confirmed Option B: full backfill — on each run, the
  system must ensure SC-001 holds for the entire journal, not just for events inserted in the
  current run. A per-file approach cannot satisfy this because it only processes events from
  the current parse, leaving pre-existing trades without offsets.
- The backfill pass is O(N) over journal rows with no I/O beyond a single read (already loaded
  in `JournalStore`) and one conditional write. For typical journal sizes, this is negligible.
- Idempotency is preserved: `missing_offset_trades()` returns an empty DataFrame when all
  offsets already exist, so no extra write occurs on re-runs.

**Alternatives considered**:
- Per-file offset generation (original design): Cannot backfill offsets for pre-existing trades
  in the journal. Rejected after clarification.
- Separate backfill CLI command: Unnecessary complexity; one-time migration is handled
  automatically on the next regular `consolidate_journals` run. Rejected.

---

## Decision 6: Summary Reporting for Offset Insertions

**Decision**: Offset rows are counted as regular insertions in the existing
`ConsolidationSummary.events_inserted` field. No separate offset-specific counter is added
to the summary data structure or the console output.

**Rationale**:
- Spec US3 (priority P3) requires that offsets be visible in the summary, but does not mandate
  a separate counter. Counting them as regular insertions satisfies the requirement with zero
  structural changes to `ConsolidationSummary`.
- Adding a new field would require changes to the summary rendering in `mode.py`, the summary
  data class in `schema.py`, and all existing tests that assert on the summary output — high
  churn for a P3 requirement.
- A user who needs to distinguish offsets from real events can filter by
  `action = "trading"` in the journal.

**Alternatives considered**:
- Add `offset_rows_inserted` field to `ConsolidationSummary`: More informative, but high
  change surface for a P3 requirement. Deferred to a future enhancement if needed.
