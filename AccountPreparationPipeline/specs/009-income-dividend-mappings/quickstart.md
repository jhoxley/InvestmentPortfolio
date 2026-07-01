# Quickstart & Test Scenarios: Income Dividend Action Mappings

**Branch**: `009-income-dividend-mappings` | **Date**: 2026-06-18

## Test Fixtures (new CSV files in `tests/data/consolidate_journals/`)

### valid_hl_st_div.csv

```csv
Trade date,Settle date,Reference,Description,Unit cost (£),Qty,Value (£)
31/03/2026,31/03/2026,ST DIV,Barclays plc Ordinary 25p Dividend Payment,,,68.38
16/09/2025,16/09/2025,ST DIV,HSBC Holdings Ordinary $0.50 Dividend Payment,,,42.10
```

Two rows with the same reference but different holdings — both must yield `dividend` events with holding-name sub-accounts.

### valid_hl_ovr_cr.csv

```csv
Trade date,Settle date,Reference,Description,Unit cost (£),Qty,Value (£)
20/05/2026,20/05/2026,OVR CR,Man Group plc ORD USD0.0342857142 Overseas Dividend Payment,,,257.69
19/09/2025,19/09/2025,OVR CR,Man Group plc ORD USD0.0342857142 Overseas Dividend Payment,,,128.85
```

### valid_hl_utc_cr.csv

```csv
Trade date,Settle date,Reference,Description,Unit cost (£),Qty,Value (£)
15/07/2025,15/07/2025,UTC CR,HSBC FTSE 250 Index Class S - Income (GBP) Eql - UT Cash Payment,,,11.85
15/07/2025,15/07/2025,UTC CR,HSBC FTSE 250 Index Class S - Income (GBP) UT Cash Payment,,,55.85
```

Both suffix variants in the same file — must both parse to the same sub-account.

### valid_hl_loyaltyu.csv

```csv
Trade date,Settle date,Reference,Description,Unit cost (£),Qty,Value (£)
15/05/2026,15/05/2026,LOYALTYU,JPMorgan Emerging Markets Class C - Accumulation (GBP) 04 26 Gross Loyalty,,,0.10
15/02/2026,15/02/2026,LOYALTYU,JPMorgan Emerging Markets Class C - Accumulation (GBP) 01 26 Gross Loyalty,,,0.09
15/08/2025,15/08/2025,LOYALTYU,JPMorgan Emerging Markets Class C - Accumulation (GBP) 07 25 Gross Loyalty,,,0.08
```

Three distinct month-year values — confirms the regex handles any two-digit month/year pair.

---

## Unit Test Scenarios

### Class: TestActionMapping (additions to existing class)

| Test name | Reference in fixture | Expected action |
|-----------|---------------------|-----------------|
| `test_st_div_reference_maps_to_dividend` | `ST DIV` | `ActionType.DIVIDEND` |
| `test_ovr_cr_reference_maps_to_dividend` | `OVR CR` | `ActionType.DIVIDEND` |
| `test_utc_cr_reference_maps_to_dividend` | `UTC CR` | `ActionType.DIVIDEND` |
| `test_loyaltyu_reference_maps_to_dividend` | `LOYALTYU` | `ActionType.DIVIDEND` |

### Class: TestDividendSubAccount (new class)

| Test name | Fixture | Input description | Expected sub_account |
|-----------|---------|-------------------|----------------------|
| `test_st_div_sub_account_strips_dividend_payment_suffix` | `valid_hl_st_div.csv` | `"Barclays plc Ordinary 25p Dividend Payment"` | `"Barclays plc Ordinary 25p"` |
| `test_ovr_cr_sub_account_strips_overseas_dividend_payment_suffix` | `valid_hl_ovr_cr.csv` | `"Man Group plc ORD USD0.0342857142 Overseas Dividend Payment"` | `"Man Group plc ORD USD0.0342857142"` |
| `test_utc_cr_eql_suffix_stripped` | `valid_hl_utc_cr.csv` | `"HSBC FTSE 250 Index Class S - Income (GBP) Eql - UT Cash Payment"` | `"HSBC FTSE 250 Index Class S - Income (GBP)"` |
| `test_utc_cr_plain_suffix_stripped` | `valid_hl_utc_cr.csv` | `"HSBC FTSE 250 Index Class S - Income (GBP) UT Cash Payment"` | `"HSBC FTSE 250 Index Class S - Income (GBP)"` |
| `test_loyaltyu_sub_account_strips_04_26_suffix` | `valid_hl_loyaltyu.csv` | `"... 04 26 Gross Loyalty"` | fund name only |
| `test_loyaltyu_sub_account_strips_01_26_suffix` | `valid_hl_loyaltyu.csv` | `"... 01 26 Gross Loyalty"` | fund name only |
| `test_loyaltyu_sub_account_strips_07_25_suffix` | `valid_hl_loyaltyu.csv` | `"... 07 25 Gross Loyalty"` | fund name only |
| `test_st_div_fallback_when_suffix_absent` | direct `_strip_dividend_suffix` call | `"ST DIV"` description with no `" Dividend Payment"` suffix | full description returned (FR-009 fallback) |
| `test_st_div_fallback_when_description_equals_suffix_only` | direct `_strip_dividend_suffix` call | `"ST DIV"` with description `" Dividend Payment"` (suffix only, no fund name) | reference string `"ST DIV"` returned as last resort (FR-009) |
| `test_loyaltyu_non_matching_pattern_raises_value_error` | direct `_strip_dividend_suffix` call | `"LOYALTYU"` with `" 4 26 Gross Loyalty"` (single-digit month) | `ValueError` raised (FR-008A) |
| `test_mixed_income_file_parses_without_error` | composed fixture or real file | ST DIV + OVR CR + UTC CR + LOYALTYU rows | 0 errors, all events returned |

---

## BDD Scenarios (additions to `tests/features/consolidate_journals.feature`)

```gherkin
  Scenario: Maps ST DIV reference to dividend action
    Given a valid HL CSV fragment with reference "ST DIV"
    When the consolidate_journals command runs against the fragment
    Then the journal contains a dividend event for that row
    And the sub_account reflects the holding name with the dividend payment suffix stripped

  Scenario: Maps OVR CR reference to dividend action
    Given a valid HL CSV fragment with reference "OVR CR"
    When the consolidate_journals command runs against the fragment
    Then the journal contains a dividend event for that row
    And the sub_account reflects the holding name with the overseas dividend suffix stripped

  Scenario: Maps UTC CR reference to dividend action
    Given a valid HL CSV fragment with two "UTC CR" rows using different description suffixes
    When the consolidate_journals command runs against the fragment
    Then the journal contains two dividend events
    And both events have the same sub_account (the fund name without any UT Cash Payment suffix)

  Scenario: Maps LOYALTYU reference to dividend action
    Given a valid HL CSV fragment with reference "LOYALTYU" across multiple months
    When the consolidate_journals command runs against the fragment
    Then the journal contains a dividend event for each row
    And all events have the same sub_account (the fund name without the month-year Gross Loyalty suffix)
```

---

## Integration Acceptance Test (manual / local only)

Run against the full HL ISA Income Account history:

```powershell
.venv\Scripts\python run_pipeline.ps1 consolidate_journals `
    --input "C:\Users\jhoxl\OneDrive\Investments\Journals\HL Stocks and Shares ISA - Income Account" `
    --account "HL ISA Income"
```

**Expected**: Summary reports `ERRORS: None` and zero dropped rows. Every row in the output CSV has a non-null, non-empty `action` value.

---

## Edge Case Test Guidance

| Scenario | How to test |
|----------|-------------|
| LOYALTYU with non-matching suffix (single-digit month) | Call `_strip_dividend_suffix("LOYALTYU", "Fund 4 26 Gross Loyalty")` directly; expect `ValueError` raised (FR-008A — regex requires two-digit month; non-match is a parse error, not a silent fallback) |
| UTC CR — longer suffix must be tried first | Covered by `test_utc_cr_eql_suffix_stripped`; sub-account must not contain `" Eql -"` |
| Empty description for dividend row | Call `_strip_dividend_suffix("ST DIV", "")` directly; expect `"ST DIV"` returned (reference fallback) |
| Leading/trailing whitespace on reference | Covered by existing whitespace-trimming in `_map_action()`; no additional test needed |
