# Data Model: Fix Cash Offset Signs

**Feature**: 006-fix-cash-offset-signs
**Date**: 2026-06-10

---

## Sign Convention (HL CSV Format)

This feature corrects the sign convention for Cash offset rows. No new entities are introduced.

### Buy Event → Cash Offset

| Field | Source (HL CSV / journal) | Offset row (corrected) |
|-------|--------------------------|------------------------|
| `date` | Trade settle date | Same as trade |
| `account` | Account label | Same as trade |
| `sub_account` | Fund name | `"Cash"` |
| `action` | `"buy"` | `"trading"` |
| `reference` | e.g. `"B12345"` | `"B12345-offset"` |
| `value` | **Negative** (e.g. `−1 000.00`) | **Same — negative** (e.g. `−1 000.00`) |
| `quantity` | Number of units | **Same as offset `value`** (e.g. `−1 000.00`) |

Cash effect in ledger: `Transaction Value = −1 000.00` → Cash `Account Value` decreases.

### Sell Event → Cash Offset

| Field | Source (HL CSV / journal) | Offset row (corrected) |
|-------|--------------------------|------------------------|
| `date` | Trade settle date | Same as trade |
| `account` | Account label | Same as trade |
| `sub_account` | Fund name | `"Cash"` |
| `action` | `"sell"` | `"trading"` |
| `reference` | e.g. `"S67890"` | `"S67890-offset"` |
| `value` | **Positive** (e.g. `+500.00`) | **Same — positive** (e.g. `+500.00`) |
| `quantity` | Number of units | **Same as offset `value`** (e.g. `+500.00`) |

Cash effect in ledger: `Transaction Value = +500.00` → Cash `Account Value` increases.

---

## Correction Summary (Bug vs Fix)

| Scenario | Buggy `value` (feature 004) | Correct `value` (this fix) |
|----------|-----------------------------|---------------------------|
| Buy (trade value = −1 000) | `+1 000` (wrong: cash appears to increase) | `−1 000` (correct: cash decreases) |
| Sell (trade value = +500) | `−500` (wrong: cash appears to decrease) | `+500` (correct: cash increases) |

---

## Rule: Offset value = Trade value (no sign inversion)

The single rule governing offset generation after this fix:

```
offset.value    = trade.value
offset.quantity = trade.value   (Cash quantity always mirrors Cash value)
```

All other fields unchanged from feature 004 contract.
