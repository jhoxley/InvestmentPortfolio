# Research: Identifier-to-Ticker Lookup

**Feature**: 005-identifier-to-ticker  
**Date**: 2026-05-12

---

## 1. yfinance Identifier Resolution

### Decision
Use `yf.Search(query, max_results=1, news_count=0)` to resolve ISIN, CUSIP, and SEDOL identifiers to ticker symbols.

### Rationale
`yf.Search` passes the query string directly to Yahoo Finance's search endpoint, which understands ISIN, CUSIP, and SEDOL formats natively. This requires no additional libraries and uses the same upstream data source as the existing pricing endpoints.

`yf.Ticker(identifier)` does **not** work reliably with raw ISINs — it attempts an internal ISIN→Yahoo-ID conversion that fails for most inputs in yfinance 0.2.x. This approach must not be used.

### Alternatives Considered
- **`yf.Ticker(isin)` directly**: Rejected — known to fail for ISINs in 0.2.x; unreliable.
- **External ISIN-to-ticker API (e.g., OpenFIGI)**: Rejected — spec assumption states no additional external service is required.
- **Vendor-provided CUSIP/SEDOL mapping tables**: Rejected — static tables would require maintenance and do not use the same data source as pricing.

### Usage Pattern
```python
import yfinance as yf

results = yf.Search(identifier, max_results=1, news_count=0)
if not results.quotes:
    raise IdentifierNotFoundError(identifier)
quote = results.quotes[0]
return {
    "ticker": quote["symbol"],
    "security_name": quote.get("longname") or quote.get("shortname") or "",
    "exchange": quote.get("exchange") or "",
}
```

### Response Fields
The `.quotes` list contains dicts with (at minimum):
- `symbol` — ticker (e.g., `"AAPL"`)
- `shortname` / `longname` — security name
- `exchange` — exchange code as returned by Yahoo Finance (e.g., `"NMS"`, `"LSE"`)
- `quoteType` — asset class (e.g., `"EQUITY"`, `"ETF"`)

Per clarification Q3 (2026-05-12), the exchange value is passed through as-is with no normalisation.

### Error Handling
yfinance `Search` raises the same network exceptions as `Ticker`:
- `requests.exceptions.ConnectionError` / `Timeout` / `RequestException` → `ProviderUnavailableError` (already defined)
- Empty `.quotes` list → `IdentifierNotFoundError` (new)

---

## 2. Identifier Format Detection

### Decision
Use pure Python `re` (stdlib) for all format detection and validation. No external library required.

### Rationale
The three identifier formats are structurally distinct and can be distinguished by length and character class alone (per clarification Q4 — structural only, no Luhn check digit computation).

### Validation Rules

| Type  | Length | Pattern                             | Notes |
|-------|--------|-------------------------------------|-------|
| ISIN  | 12     | `^[A-Z]{2}[A-Z0-9]{10}$`           | First 2 chars: ISO 3166-1 country code (uppercase alpha); last 10: alphanumeric |
| CUSIP | 9      | `^[A-Z0-9]{9}$`                     | 9 alphanumeric (US and Canada) |
| SEDOL | 6–7    | `^[A-Z0-9]{6,7}$`                   | 6 or 7 alphanumeric (UK / international) |

All patterns applied after normalising the identifier to uppercase.

### Auto-Detection Priority (no type hint)
1. ISIN — if length == 12 and first 2 chars match `[A-Z]{2}`
2. CUSIP — if length == 9
3. SEDOL — if length == 6 or 7
4. None match → `IdentifierFormatError` (422)

### Type-Hint Override
If the caller provides a type hint:
- Validate only against the specified type's pattern.
- If the format does not match → `IdentifierFormatError` (422).

### Alternatives Considered
- **`stdnum` library**: Rejected — adds a dependency; stdlib regex is sufficient for structural checks.
- **Luhn check digit validation for ISIN**: Rejected per clarification Q4 (2026-05-12).

---

## 3. New Exceptions

| Exception | HTTP | Code |
|---|---|---|
| `IdentifierFormatError` | 422 | `IDENTIFIER_FORMAT_ERROR` |
| `IdentifierNotFoundError` | 404 | `IDENTIFIER_NOT_FOUND` |
| `ProviderUnavailableError` | 503 | `PROVIDER_UNAVAILABLE` (existing) |

---

## 4. Interface Design

### `IdentifierProvider` ABC (new)
Placed in `app/providers/identifier_provider.py` to keep it separate from `PricingProvider` (Interface Segregation).

```python
class IdentifierProvider(ABC):
    @abstractmethod
    def lookup_ticker(self, identifier: str, identifier_type: str) -> dict[str, object]:
        ...
```

Returns dict with keys: `ticker`, `security_name`, `exchange`.

### `YFinanceIdentifierProvider(IdentifierProvider)`
Concrete implementation using `yf.Search`. Raises `ProviderUnavailableError` on network failure, `IdentifierNotFoundError` on empty results.

### `IdentifierService`
Orchestrates: normalise → detect/validate type → delegate to provider → return `TickerResolutionResponse`.

---

## 5. Endpoint Design

```
GET /identifiers/{identifier}?type={ISIN|CUSIP|SEDOL}
```

- `identifier` (path, required): the raw identifier string
- `type` (query, optional): type hint; triggers type-specific format validation instead of auto-detection

Router prefix: `/identifiers`, tag: `Identifiers`.
