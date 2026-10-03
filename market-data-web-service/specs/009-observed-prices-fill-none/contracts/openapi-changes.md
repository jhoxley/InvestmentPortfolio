# Phase 1 Contract Changes: Observed-Only Price History (`fill=none`)

**Feature**: `specs/009-observed-prices-fill-none` | **Date**: 2026-10-03
**Target file**: `openapi.yaml` (authoritative contract — per constitution VI, edited **before** any
implementation task)
**Version**: `info.version` `0.1.2` → `0.1.3` (additive, backwards-compatible — no major bump)

Only `GET /securities/{ticker}/history` and the `PriceHistoryResponse` schema change. The current-price
endpoint, `GET /fx/{pair}/history`, the cache endpoints and the identifier endpoints are untouched.

---

## 1. New query parameter on `/securities/{ticker}/history`

Add after the existing `currency` parameter:

```yaml
      - name: fill
        in: query
        required: false
        description: >
          Series shaping mode.

          `all` (default) returns a value for every Mon–Fri business day in the requested
          range, filling gaps from holidays or data outages by forward/backward carry of the
          nearest observation — the behaviour of all prior versions.

          `none` returns only dates that have a real market observation from the primary
          source, the cache, or a configured local fallback file. No date is manufactured, so
          the series may be shorter than the requested range and may skip business days. Use
          this when genuine day-to-day returns matter, for example a Value-at-Risk
          calculation, where a carried-forward flat price would be indistinguishable from a
          real zero-return day.

          Any other value is rejected with 422.
        schema:
          allOf:
          - $ref: '#/components/schemas/FillMode'
          default: all
          title: Fill
```

### New named schema component

Per constitution VI, inline anonymous schemas are prohibited, so the enum is a named component:

```yaml
    FillMode:
      type: string
      enum:
      - all
      - none
      title: FillMode
      description: >
        Series shaping mode for price history. `all` gap-fills every business day;
        `none` returns observed prices only.
```

---

## 2. Two new properties on `PriceHistoryResponse`

Add to `components.schemas.PriceHistoryResponse.properties`. Both are **additive and nullable**; the
`required` list is NOT extended, so existing consumers that validate against the old schema continue to
pass.

```yaml
        first_observed_date:
          anyOf:
          - type: string
            format: date
          - type: 'null'
          title: First Observed Date
          description: >
            Earliest date for which the service knows of a real market observation for this
            instrument, as far as the service knows — derived from stored history plus anything
            fetched while serving this request. Independent of the requested range: it may be
            earlier than the `from` parameter. Never derived from a gap-filled value. Populated
            in both fill modes.
          example: '2024-03-01'
        last_observed_date:
          anyOf:
          - type: string
            format: date
          - type: 'null'
          title: Last Observed Date
          description: >
            Latest date for which the service knows of a real market observation for this
            instrument. May be later than the `to` parameter. Never derived from a gap-filled
            value. Populated in both fill modes.
          example: '2025-06-30'
```

Resulting schema (unchanged parts elided):

```yaml
    PriceHistoryResponse:
      properties:
        ticker: ...
        currency: ...
        prices: ...
        first_observed_date: ...   # NEW
        last_observed_date: ...    # NEW
      type: object
      required:
      - ticker
      - currency
      - prices                      # unchanged — the new fields are not required
      title: PriceHistoryResponse
```

---

## 3. Revised `200` description

The existing description promises a complete business-day series unconditionally. It must now be
mode-dependent. Replace the first paragraph and append a mode note; the sub-unit normalisation paragraph
is retained verbatim.

```yaml
      responses:
        '200':
          description: >
            Price history returned (translated if currency parameter provided).

            **`fill=all` (default)**: all Mon–Fri business days in the requested range are
            guaranteed to have an entry — gaps from holidays or data outages are filled by
            forward/backward carry of the nearest observation.

            **`fill=none`**: only dates with a real market observation are returned. Business
            days without an observation are absent, the series is not extended to the requested
            start or end date, and no value is ever carried. A weekend-dated observation, if the
            source holds one, is returned as the real observation it is.

            **Observation window**: `first_observed_date` and `last_observed_date` report the
            instrument's known observation range in both modes, independent of the requested
            range, so a consumer can size a lookback window without exploratory requests.

            **Currency conversion**: unchanged in both modes. Each returned price is converted at
            the gap-filled FX rate for its own date, so a missing raw FX rate can never drop a
            real price observation. Conversion adds no dates under `fill=none`.

            **Sub-unit currency normalisation**: Same normalisation as the `/price` endpoint
            applies. All `close` values in the returned series are in major-unit terms, and the
            `currency` field reflects the major-unit code. If a `currency` query parameter is
            provided for FX conversion, normalisation is applied first so the FX rate is applied
            to major-unit values.
```

---

## 4. Revised `404` description

The 404 condition now explicitly covers an empty result in either mode, aligning the contract with
feature 006's FR-008 and this feature's FR-009 (see the Behaviour Change note in `plan.md`).

```yaml
        '404':
          description: >
            Ticker not found, FX alignment failed, or no observation exists within the requested
            range. The empty-range case applies to both fill modes: a range containing no
            observations is a not-found response, never a 200 with an empty `prices` list.
```

---

## 5. Unchanged by this feature

- `GET /securities/{ticker}/price` — no `fill` parameter, no new fields.
- `GET /fx/{pair}/history` — FX rate series remains gap-filled unconditionally, by design: a filled rate
  is preferable to dropping a real price observation (research R6).
- `PricePoint`, `PriceResponse`, `FxHistoryResponse`, `FxRateEntry`, `ErrorResponse` — no changes.
- The `422` and `503` descriptions — the new parameter's rejection is already covered by the existing
  `HTTPValidationError` response, which will carry `loc: ["query", "fill"]`.

---

## Contract verification

- `openapi.yaml` must validate with no errors (constitution quality gate).
- The hand-maintained `openapi.yaml` must match what FastAPI generates from the implementation at
  `/openapi.json` for the changed paths and schemas — in particular the `FillMode` enum values and the
  two new nullable date properties.
- Swagger UI at `/docs` must show `fill` as a dropdown with `all` preselected.
