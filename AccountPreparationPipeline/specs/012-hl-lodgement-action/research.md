# Research: HL Lodgement Action Mapping

**Feature**: 012-hl-lodgement-action
**Date**: 2026-07-02

## Decision 1: Regex Pattern for Lodgement Reference Detection

**Decision**: Use `re.compile(r"^L\d+$")` as the lodgement detection pattern — exactly mirroring
`RE_BUY = re.compile(r"^B\d+$")` and `RE_SELL = re.compile(r"^S\d+$")` already in
`src/modes/consolidate_journals/constants.py`.

**Rationale**: All three transaction types (buy, sell, lodgement) share the same HL reference
format: a single uppercase letter followed by one or more digits, with no other characters. Using
the same regex structure ensures consistency and makes the pattern immediately recognisable to
maintainers. The `^` and `$` anchors guarantee exact matching — `L003538235` matches, but
`LOYALTYU` and `L-invalid` do not, which satisfies FR-008.

**Alternatives considered**: Check `ref.upper().startswith("L") and ref[1:].isdigit()` inline.
Rejected — a compiled regex constant is consistent with existing style, slightly faster for
repeated calls, and centralises the pattern in `constants.py` for audit.

---

## Decision 2: Sub-Account Derivation — Prefix Strip Strategy

**Decision**: Strip the literal string `"Lodgement "` (capital L, trailing space) from the
start of the description using `description.removeprefix("Lodgement ")`. If the result is
non-empty, it becomes the sub-account. If the description does not start with the prefix (or
stripping leaves an empty string), fall back to the full description; if description is also
empty, fall back to the reference.

**Rationale**: All observed examples follow the pattern exactly — `"Lodgement "` is always the
first 10 characters of the description for lodgement rows. `str.removeprefix()` (Python 3.9+,
well within the Python 3.11+ requirement) is idiomatic and does not raise if the prefix is
absent, which handles the edge case in FR-004 cleanly. No regex is needed since the prefix is
a fixed string.

**Alternatives considered**: Use `re.sub(r"^Lodgement\s+", "", description)`. Rejected — the
prefix is exactly `"Lodgement "` with one space in all real data; a regex would be over-engineered
for this fixed pattern. Using `removeprefix` is more readable and directly expresses intent.

---

## Decision 3: Sign Convention — Store Value As-Is

**Decision**: The value from the lodgement CSV row is stored as-is (negative, representing
outflow/cost-basis). No sign adjustment is applied in the parser.

**Rationale**: The existing HL parser applies no sign adjustment to any action type — it calls
`_parse_decimal(value_raw)` and stores the result directly in `JournalEvent.value`. The
downstream ledger engine (`create_ledger`) handles sign semantics (e.g., buy values being
negated for `Transaction Value`). Lodgements should behave identically to buy transactions:
negative value in the raw CSV → negative value in the journal → `create_ledger` applies its
own sign convention when building the ledger.

**Alternatives considered**: Negate the value to make it positive (matching "inflow" semantics).
Rejected — this would be inconsistent with how buy transactions are stored and would require
downstream changes to `create_ledger` to handle lodgements as a distinct case.

---

## Decision 4: Cash Offsets for Lodgements — Out of Scope

**Decision**: Lodgement transactions do NOT generate synthetic cash offset rows in this feature.
`CASH_ACTION_TYPES` is unchanged; `missing_offset_trades()` and `rectify_offsets()` in
`journal_store.py` are not modified.

**Rationale**: The spec (FR-006) states only that lodgements are not cash transactions. No
requirement mentions cash offsets for lodgements. In-specie lodgements don't involve a cash
movement — the securities arrive at market value with no corresponding Cash sub-account entry.
Adding offset logic would be a separate feature if ever needed.

**Alternatives considered**: Generate a cash offset (mirroring BUY/SELL offset logic). Rejected
— unspecified and inappropriate for in-specie transfers.

---

## Decision 5: Insertion Point in `_map_action()`

**Decision**: Insert the lodgement check immediately after the sell check, before the deposit
check, in `_map_action()` in `src/modes/consolidate_journals/parsers/hl.py`.

**Rationale**: The check order in `_map_action` proceeds from most-specific (regex patterns:
buy, sell) to least-specific (string lookups: deposit, income, dividend). Lodgement follows the
same letter+digits pattern as buy and sell and belongs in the regex-pattern group. Inserting
it immediately after sell maintains logical grouping.

**Alternatives considered**: Insert at the end before the `raise ValueError`. Rejected — the
ordering signals intent; a pattern-matched check belongs near the other pattern-matched checks.

---

## Decision 6: No New Source Files

**Decision**: All changes are modifications to existing files. No new modules, no new
`constants.py` files, no new parsers.

**Rationale**: The lodgement action is an extension of the existing HL parser behaviour, not a
new subsystem. Adding it to the existing files (schema, constants, parser) is the minimal,
correct change. Creating new files would violate Single Responsibility by splitting closely
related parser constants.

**Alternatives considered**: Create a separate `lodgement_handler.py` module. Rejected — the
lodgement detection and sub-account derivation is 3–4 lines of code, comparable to buy/sell
handling which is inline in `_map_action` and `_parse_row`. A separate module would be
over-engineering.
