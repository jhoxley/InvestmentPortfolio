# Contract Delta: `GET /v1/accounts/{account_name}/projection`

Baseline: `specs/009-projection-endpoint/contracts/projection-api.md`. Only the items below change.

## Unchanged

Path, query parameters, status codes, RFC 7807 errors, `_links`, response schema, and the
historical series.

## Changed semantics (documentation only; OpenAPI schema is unchanged)

For `periodicity` in `week | month | quarter | annual`, each projected series:

1. begins at the first window-start business day **on or after** the resolved start — the resolved
   start itself appears only when it is already a window start;
2. ends at the last window start on or before `projection_date`;
3. may be empty (return then absent from `positions`) when no window start falls in range.

For `periodicity=day` there is no change: the series begins at the resolved start.

## Example

`?projection_date=2026-12-31&return=3Y&start=2026-09-22&periodicity=month`

- `Historical`: …, 2026-08-03, 2026-09-01 (unchanged)
- `3Y`: **2026-10-01**, 2026-11-02, 2026-12-01 (previously also 2026-09-22)

Action: append a sentence describing rule 1–2 to the endpoint's OpenAPI description in
`app/api/projection.py`.
