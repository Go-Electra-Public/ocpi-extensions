# End-user pricing display — OCPI 2.1.1

**Status:** Draft, under review, not ready for implementation
**Applies to:** OCPI 2.1.1 connections
**Roles:** the eMSP hosts the module, the CPO calls it
**Other versions:** [OCPI 2.2.1](ocpi-2.2.1.md)

The key words MUST, MUST NOT, SHOULD, SHOULD NOT and MAY are to be interpreted as described in
[RFC 2119](https://www.rfc-editor.org/rfc/rfc2119).

Read [`README.md`](README.md) first for the rationale, the design principles and the cost
semantics. This document is the normative wire contract.

> [!WARNING]
> **Note on 2.1.1.** OCPI 2.1.1 defines every amount as excluding VAT (`Session.total_cost`,
> `CDR.total_cost`, `PriceComponent.price`) and has no VAT field. The driver pays VAT, so this
> extension deviates from 2.1.1: every amount it carries is **VAT-inclusive**, and each object
> states this explicitly (`prices_incl_vat`, `end_user_total_cost_incl_vat`). An eMSP MUST NOT
> reuse its standard 2.1.1 tariff serializer without changes. Check §3.4 and §4.4 carefully.

---

## 1. Overview

The extension adds one module, `end_user_pricing`, hosted by the **eMSP** and called by the
**CPO**. It has two endpoints:

| # | Endpoint | Method | Returns |
| --- | --- | --- | --- |
| 1 | `{end_user_pricing_url}/tariffs/{country_code}/{party_id}/{location_id}[/{evse_uid}[/{connector_id}]]` | GET | `EndUserTariffs`: a `PricingStatus` and one OCPI 2.1.1 `Tariff` per connector |
| 2 | `{end_user_pricing_url}/session_costs/{country_code}/{party_id}/{session_id}` | GET | `EndUserSessionCost` |

No existing OCPI message is modified. No endpoint is added on the CPO side.

The eMSP is the **source of truth** for everything this module returns: it sets the driver's
tariff, computes the driver's cost and bills the driver. The CPO consumes and displays these
values as received. It MUST NOT compute, correct or complete a driver-facing price from other
data. In 2.1.1 the CPO performs no computation at all: any VAT that applies is already included
in the amounts it receives.

**Best effort on both sides.** Everything this module carries is informational. The price may
change after the session starts (promotion, discount, eMSP-side rule). The eMSP makes a best
effort to return the tariff and cost it will bill, and the CPO makes a best effort to display
them to the driver. Neither party guarantees the displayed figures: the eMSP's invoice to the
driver is the only reference for billing.

The CPO SHOULD display, next to any roaming price or cost from this module, a notice that the
figure is indicative and that the eMSP's pricing conditions apply. This is best-effort:
charge-point screens are not fully configurable, so on some models the notice may be shortened
or missing.

Both endpoints use the standard OCPI response envelope (`data`, `status_code`,
`status_message`, `timestamp`) and the standard `Authorization: Token` credentials of the
connection.

Future versions of this extension MAY add optional fields to its objects. A receiver MUST
ignore fields it does not know.

### 1.1 PricingStatus enum

Both endpoints return a `pricing_status` that tells the CPO whether, and when, a driver-facing
price exists. It is what lets an eMSP say "this session is not priced live" instead of leaving
the CPO to poll for nothing.

| Value | Meaning | CPO behaviour |
| --- | --- | --- |
| `AVAILABLE` | A driver-facing price exists and is included in the response. | Display it. Keep polling the session cost after each push. |
| `PENDING` | The session or token is priced live, but the eMSP cannot give a figure right now (push not yet processed, pricing service late, contract resolution in progress). | Keep the last displayed value, if any. Keep polling after each push. |
| `NOT_AVAILABLE` | No live driver-facing price will exist for this token or session. Typical cases: B2B contract with month-end volume discounts, post-paid or subscription pricing settled on invoice, free-of-charge arrangements handled outside the session. | Show no roaming price. Do not poll the session cost for this session. |

---

## 2. Module registration

### 2.1 Version details

The eMSP lists the module in the endpoints of its version-details response:

```json
{
  "identifier": "end_user_pricing",
  "url": "https://emsp.example.com/ocpi/2.1.1/end_user_pricing"
}
```

### 2.2 Requirements

- The `identifier` MUST be `end_user_pricing`. It is not a value of the standard `ModuleID`
  enum: the eMSP MUST list it only on connections where the extension has been agreed, and a
  CPO that has not enabled the extension MUST ignore the entry.
- Because some OCPI implementations validate `identifier` strictly, both parties MAY instead
  configure the module URL manually for the connection. The URL is the only thing the CPO
  needs.
- The module is enabled per connection, by agreement. A CPO MUST NOT call the module on a
  connection where it has not been agreed, even if the endpoint is listed.

---

## 3. Tariffs endpoint

### 3.1 Request

```
GET {end_user_pricing_url}/tariffs/{country_code}/{party_id}/{location_id}[/{evse_uid}[/{connector_id}]]?token_uid={token_uid}[&token_type={token_type}]
```

The path follows the eMSP-side Locations module. Requesting the Location returns every
connector the eMSP can price there; adding `evse_uid`, then `connector_id`, narrows the answer.

| Parameter | Type | Card. | Description |
| --- | --- | --- | --- |
| `country_code` | `string(2)` | 1 | Path. Country code of the CPO that owns the Location, as in the Locations module. |
| `party_id` | `string(3)` | 1 | Path. Party id of the CPO that owns the Location. |
| `location_id` | `string(39)` | 1 | Path. `Location.id` of the Location the driver is at. |
| `evse_uid` | `string(39)` | ? | Path. Restricts the answer to one EVSE of the Location, by `EVSE.uid` (not `evse_id`). |
| `connector_id` | `string(36)` | ? | Path. Restricts the answer to one connector of that EVSE. Requires `evse_uid`. |
| `token_uid` | `string(36)` | 1 | Query. `uid` of the token presented by the driver. |
| `token_type` | `TokenType` | ? | Query. `type` of the token presented by the driver. Default if omitted: `RFID`. The CPO SHOULD always send it when it knows the type (from `authorize` or `START_SESSION`): with the wrong type the token is unknown to the eMSP. |

2.1.1 has two token types, `RFID` and `OTHER`, and a token is identified by `uid` + `type`.
`token_type` mirrors the optional `type` parameter of the 2.1.1 `authorize` endpoint, with the
same `RFID` default.

Example:

```http
GET /ocpi/2.1.1/end_user_pricing/tariffs/FR/ABC/LOC001?token_uid=12345678
Authorization: Token <token>
```

### 3.2 Response

`data` is an `EndUserTariffs` object:

| Field | Type | Card. | Description |
| --- | --- | --- | --- |
| `pricing_status` | `PricingStatus` | 1 | Whether this token is priced live (§1.1). `NOT_AVAILABLE` applies to the whole session that follows: the CPO will not call the session cost endpoint for it. |
| `tariffs` | `EndUserTariff` | * | One entry per connector of the requested scope the eMSP can price. Empty when `pricing_status` is not `AVAILABLE`, and MAY be empty with `AVAILABLE` when no connector could be priced. |

`EndUserTariff`:

| Field | Type | Card. | Description |
| --- | --- | --- | --- |
| `evse_uid` | `string(39)` | 1 | EVSE of the requested Location this tariff applies to: its `EVSE.uid`, not its `evse_id`. |
| `connector_id` | `string(36)` | 1 | `Connector.id` within that EVSE this tariff applies to. |
| `tariff` | `Tariff` | 1 | The OCPI 2.1.1 `Tariff` the eMSP applies to this driver, for this token, at this connector. |
| `prices_incl_vat` | `boolean` | 1 | MUST be `true`. Confirms that every `price` in `tariff` is VAT-inclusive, which reverses the 2.1.1 meaning of `PriceComponent.price`. The CPO MUST discard an entry where this field is missing or `false`. |

`Tariff` has the shape of the standard OCPI 2.1.1 object, unchanged. Note that in 2.1.1 it has
no `country_code`, `party_id` or `type`, and its price components have no `vat`. Its `price`
values are VAT-inclusive, unlike standard 2.1.1 (§3.4).

```json
{
  "data": {
    "pricing_status": "AVAILABLE",
    "tariffs": [
      {
        "evse_uid": "3256",
        "connector_id": "1",
        "prices_incl_vat": true,
        "tariff": {
          "id": "xyz-dc-2026-09",
          "currency": "EUR",
          "elements": [
            {
              "price_components": [
                { "type": "ENERGY", "price": 0.59, "step_size": 1 }
              ]
            },
            {
              "price_components": [
                { "type": "PARKING_TIME", "price": 7.2, "step_size": 60 }
              ],
              "restrictions": { "min_duration": 1800 }
            }
          ],
          "last_updated": "2026-09-17T09:00:00Z"
        }
      },
      {
        "evse_uid": "3257",
        "connector_id": "1",
        "prices_incl_vat": true,
        "tariff": {
          "id": "xyz-dc-2026-09",
          "currency": "EUR",
          "elements": [
            {
              "price_components": [
                { "type": "ENERGY", "price": 0.59, "step_size": 1 }
              ]
            }
          ],
          "last_updated": "2026-09-17T09:00:00Z"
        }
      }
    ]
  },
  "status_code": 1000,
  "status_message": "Success",
  "timestamp": "2026-09-17T09:12:00Z"
}
```

Token under a contract with no live price (for example a B2B fleet billed monthly with volume
discounts):

```json
{
  "data": {
    "pricing_status": "NOT_AVAILABLE",
    "tariffs": []
  },
  "status_code": 1000,
  "status_message": "Success",
  "timestamp": "2026-09-17T09:12:00Z"
}
```

### 3.3 When the CPO calls it

| Flow | Trigger | Purpose |
| --- | --- | --- |
| Token presented, real-time authorization | Immediately after the `POST /tokens/{token_uid}/authorize` response with `allowed` = `ALLOWED`. The call does not delay the authorization outcome. | Show the driver's tariff before they plug in |
| Token presented, whitelisted `ALWAYS` / `ALLOWED_OFFLINE` | When the token is presented; no `authorize` call precedes it. | Show the driver's tariff before they plug in |
| Remote start (`START_SESSION`) | Optional, on receipt of the command. The driver already saw the price in the eMSP app. | Show the driver's tariff if it arrives before plug-in |

The CPO SHOULD request the whole Location the driver is at (no `evse_uid`), since the driver has
not yet chosen a connector. It MAY narrow the request to one EVSE or one connector when it knows
which one the driver uses.

### 3.4 Requirements

- The tariff MUST be the price the **eMSP bills the driver**, not the CPO's price to the eMSP.
- `currency` inside the `Tariff` object MUST be the currency the eMSP bills the driver in.
- **`price` values MUST include the VAT that applies to this driver, if any, and
  `prices_incl_vat` MUST be `true`.** This reverses the standard 2.1.1 meaning (excluding VAT).
  2.1.1 has no VAT rate field, so the CPO cannot add VAT itself.
- Tariffs can differ between connectors of the same EVSE (for example AC and DC). The eMSP
  SHOULD return one entry per connector it can price. Before plug-in, the CPO MAY display the
  entries of all connectors; once the connector is known, it displays the matching entry.
- The eMSP MUST omit a connector from `tariffs` rather than return a placeholder tariff when it
  cannot resolve a price for it. A `Tariff` with no `elements` MUST NOT be returned. `AVAILABLE`
  with an empty `tariffs` array is a valid answer meaning "priced live, but no tariff to display
  at these connectors".
- `pricing_status` MUST be `NOT_AVAILABLE` when the eMSP knows that no live driver-facing price
  will exist for this token (§1.1). It is the eMSP's only way to prevent the CPO from polling
  the session cost for the whole session, so it SHOULD be used whenever the contract type is
  known at tariff time.
- The eMSP MAY return the same `Tariff` object for several connectors; the CPO does not
  deduplicate on `Tariff.id`.
- The tariff MUST be self-contained. `Tariff.id` is opaque to the CPO: the CPO does not look it
  up, cache it across sessions, or fetch it from the `Tariffs` module.
- The tariff is valid for the session about to start. The CPO MUST NOT reuse it for a later
  session of the same token.

### 3.5 Error handling

- The CPO applies a timeout to this request. Its value is part of the per-connection agreement,
  not of this specification; it is short, since the charge-point screen can show the tariff
  only before the driver plugs in. A late answer is discarded. The tariff can still reach the
  driver through the session cost endpoint (§4.2).
- Any `status_code` other than `1000`, a transport error or a timeout MUST NOT affect the
  authorization or the session. The CPO simply does not display a roaming price.
- The eMSP MUST answer `2001` for a malformed request (missing `token_uid`, `connector_id`
  without `evse_uid`). For an unknown token it SHOULD answer `1000` with `pricing_status`
  `NOT_AVAILABLE` rather than an error; for an unknown Location, EVSE or connector, `1000` with
  no entry for it in `tariffs`. The extension is best-effort and an error code would only add
  noise for a normal situation.

---

## 4. Session cost endpoint

### 4.1 Request

```
GET {end_user_pricing_url}/session_costs/{country_code}/{party_id}/{session_id}
```

| Parameter | Type | Card. | Description |
| --- | --- | --- | --- |
| `country_code` | `string(2)` | 1 | Country code of the CPO that pushed the session, as in the eMSP-side Sessions module. |
| `party_id` | `string(3)` | 1 | Party id of the CPO that pushed the session. |
| `session_id` | `string(36)` | 1 | `id` of the session as pushed by the CPO with `PUT /sessions`. |

```http
GET /ocpi/2.1.1/end_user_pricing/session_costs/FR/ABC/8b1e2c4a-5d3f-4e6a-9b7c-0d1e2f3a4b5c
Authorization: Token <token>
```

### 4.2 Response

`data` is an `EndUserSessionCost` object, always present on a `1000` response. The three cost
fields are present if and only if `pricing_status` is `AVAILABLE`.

| Field | Type | Card. | Description |
| --- | --- | --- | --- |
| `pricing_status` | `PricingStatus` | 1 | Whether a driver-facing cost exists for this session (§1.1). |
| `end_user_total_cost_incl_vat` | `number` | 1 if `AVAILABLE` | Cumulative, **VAT-inclusive** cost of the session to the driver, as of `last_updated`. |
| `currency` | `string(3)` | 1 if `AVAILABLE` | ISO 4217 code of the currency of `end_user_total_cost_incl_vat`. |
| `last_updated` | `DateTime` | 1 if `AVAILABLE` | Moment at which the eMSP computed this cost. The cost is cumulative as of this moment. Standard OCPI `last_updated` semantics: when this object last changed. |
| `tariff` | `Tariff` | ? | Tariff the eMSP applies to this session as of `last_updated`, for example after a promotion activated at session start. Same rules as §3.4. When present, it replaces the §3 tariff for display. When absent, the CPO keeps the §3 tariff. Only allowed with `AVAILABLE`. |
| `prices_incl_vat` | `boolean` | 1 if `tariff` | MUST be `true`, as in `EndUserTariff` (§3.2). The CPO MUST ignore a `tariff` without it. |

The type of `end_user_total_cost_incl_vat` mirrors 2.1.1 `Session.total_cost` (a plain number,
no VAT breakdown), but the VAT meaning is the opposite: `Session.total_cost` excludes VAT.

```json
{
  "data": {
    "pricing_status": "AVAILABLE",
    "end_user_total_cost_incl_vat": 4.92,
    "currency": "EUR",
    "last_updated": "2026-09-17T09:12:00Z"
  },
  "status_code": 1000,
  "status_message": "Success",
  "timestamp": "2026-09-17T09:12:03Z"
}
```

Session not yet priced (push not processed, pricing late):

```json
{
  "data": { "pricing_status": "PENDING" },
  "status_code": 1000,
  "status_message": "Success",
  "timestamp": "2026-09-17T09:12:03Z"
}
```

Session that will never be priced live (settled on the monthly invoice):

```json
{
  "data": { "pricing_status": "NOT_AVAILABLE" },
  "status_code": 1000,
  "status_message": "Success",
  "timestamp": "2026-09-17T09:12:03Z"
}
```

### 4.3 When the CPO calls it

| Step | OCPI | Purpose |
| --- | --- | --- |
| Session start | `PUT /sessions` (`ACTIVE`), then one `GET …/session_costs/…` | Initial running cost, usually zero |
| Charging | each `PUT`/`PATCH /sessions`, then one `GET …/session_costs/…` | Running cost |
| Session end | final `PUT` (`COMPLETED`), then one `GET …/session_costs/…` | Provisional final cost |

- The CPO MUST call the endpoint only **after** the corresponding session push has been
  acknowledged with `status_code` `1000`, so that the eMSP has the state it is asked to price.
- The CPO SHOULD NOT call it more than once per session push it has sent. It MAY retry after a
  timeout or a transport error, since the answer only depends on the session state the eMSP
  holds. The refresh rate of the displayed cost is therefore bounded by the session-push
  cadence, which is agreed per connection like any other OCPI operational parameter.
- The CPO MUST NOT call the endpoint at all for a session whose tariffs response (§3) said
  `NOT_AVAILABLE`, and MUST stop calling it once a response says `NOT_AVAILABLE`.
- After `COMPLETED`, the CPO MAY retry once after a short delay if the answer was `PENDING`,
  then stops.

### 4.4 Semantics

- **Cumulative.** `end_user_total_cost_incl_vat` is the total for the session so far, not a
  delta.
- **Freshness.** `last_updated` is the moment the eMSP computed the figure, on its own clock. It
  does not have to match any `last_updated` the CPO pushed: how the eMSP derives the cost, from
  the CPO's session updates or from inputs of its own (promotions, credits, wall-clock fees), is
  the eMSP's business. The CPO uses it only to judge staleness and to discard an answer older
  than the one it already displays.
- **VAT.** The value MUST include the VAT that applies to this driver, if any, as it is
  displayed as-is and 2.1.1 offers no way to express a breakdown. This reverses the 2.1.1
  meaning of `Session.total_cost`. Leaving out VAT that applies understates the price on the
  screen.
- **Currency.** In the currency the eMSP bills the driver in, which MUST be the `currency` of
  the tariffs returned for the session. The CPO performs no conversion.
- **Final value.** The answer following the `COMPLETED` push is treated as the **provisional
  final cost**. It is informational: the eMSP's invoice to the driver prevails.
- **`PENDING`.** The eMSP cannot give a figure at this time but expects to. The CPO keeps the
  last displayed value, or shows no roaming cost if there is none, and polls again after its
  next push.
- **`NOT_AVAILABLE`.** No live figure will exist for this session. The CPO shows no roaming cost
  and stops polling. An eMSP MUST NOT switch a session from `AVAILABLE` back to
  `NOT_AVAILABLE`; once it has priced a session live it keeps doing so, using `PENDING` for
  transient gaps.
- **Decreases.** The cost is normally non-decreasing, but it MAY decrease, for example when a
  promotion or credit is applied during the session. The CPO displays the value as received.
- **Unrelated to the CDR.** See [Cost semantics](README.md#cost-semantics-in-one-place).

### 4.5 Tariff and session

- The tariff returned by §3 before the session is displayed until the session cost endpoint
  returns a `tariff` (§4.2), which then replaces it. The eMSP SHOULD return `tariff` whenever
  the tariff applied to the session differs from the §3 one, for example after a promotion
  activated at session start or a change mid-session. Whatever the eMSP bills is reflected by
  the running cost (§4) and by its invoice, which prevails.
- Consequently, if the eMSP wants time-dependent pricing (time-of-day bands, parking fee after a
  delay) to be visible to the driver before plug-in, it SHOULD express it with
  `TariffElement.restrictions` inside the `Tariff`, as standard OCPI intends.

### 4.6 Error handling

- The CPO applies a timeout to this request, agreed per connection. When it expires the
  previously displayed value is kept and the answer, if it arrives later, is discarded.
- Any `status_code` other than `1000`, a transport error or a timeout MUST NOT affect the
  session or the CDR.
- For an unknown session the eMSP SHOULD answer `1000` with `PENDING`, not an error: the push
  may simply not have been processed yet. It MUST answer `2001` for a malformed path.

---

## 5. Rendering (informative)

This section is **not normative**. How a CPO renders the objects it receives is at its
discretion. It describes one CPO implementation, a charge-point screen driven by OCPP 1.6
California Pricing, so that a tariff can be authored with such a screen in mind.

- **Supported price component types.** `ENERGY`, `PARKING_TIME`, `TIME` and `FLAT`. These are
  the four `TariffDimensionType` values, so no component type is structurally unsupported — but
  a tariff built mostly from `FLAT` and `TIME` components renders as a longer, less readable
  string than an energy-based one.
- **Restrictions.** Rendered on a best-effort basis, at the CPO's discretion. Simple
  restrictions that map to a threshold the screen can state, such as `min_duration` on a parking
  component, are the ones most likely to be shown. Complex combinations may be summarised or
  left out. An eMSP should not rely on any specific restriction being displayed.
- **Overstay.** A time-based overstay is expressed with `PARKING_TIME` or `TIME` plus
  `min_duration`. OCPI has no state-of-charge restriction; the closest standard proxy for "fee
  once the battery is nearly full" is `TIME` with a `max_power` restriction. An eMSP billing a
  genuinely SoC-based overstay cannot announce it in the tariff; the driver sees it only in the
  running cost.
- **Partial rendering.** When part of a tariff cannot be rendered, the screen shows what can be
  and leaves the rest out, rather than showing nothing. Free-text fields of the `Tariff` are not
  used for the screen.
- **Indicative notice.** Where the screen allows it, a line is shown next to any roaming price
  or cost, such as *Indicative price, your provider's conditions apply*. The exact wording is up
  to each CPO.
- **Other channels.** This section covers the charge-point screen. Other channels, such as
  messages sent to the driver during the session, may show the full tariff, including a
  `tariff` received from §4.2.
- **Locale.** The screen is rendered in the station's locale, not the driver's.
- **Refresh rate.** Bounded by the session-push cadence, see §4.3.
- **`NOT_AVAILABLE`.** What the screen shows for a driver whose eMSP declares no live price is
  up to each CPO, for example nothing, or a generic "billed by your provider" line.

---

## 6. Differences from OCPI 2.2.1

| | 2.1.1 (this document) | 2.2.1 |
| --- | --- | --- |
| Tariffs request | path `…/tariffs/{country_code}/{party_id}/{location_id}[/{evse_uid}[/{connector_id}]]`, query `token_uid` · `token_type` | same |
| `Tariff` object | 2.1.1 `Tariff` — no `country_code`/`party_id`, no `type`, no `vat` on price components, no `min_price`/`max_price` | 2.2.1 `Tariff`, with `country_code`/`party_id` of the eMSP role |
| Tariff prices | VAT-**inclusive**, stated by `prices_incl_vat: true` | excluding VAT, with `vat` percentage per component |
| Session cost path | `…/session_costs/{country_code}/{party_id}/{session_id}` | same |
| End-user total cost | `end_user_total_cost_incl_vat`: `number`, VAT-inclusive | `end_user_total_cost`: `Price { excl_vat, incl_vat }` |
| Endpoint registration | `identifier` · `url` | `identifier` · `role: SENDER` · `url` |

---

## 7. Naming

The module identifier `end_user_pricing`, the enum `PricingStatus` and the fields
`pricing_status`, `tariffs`, `evse_uid`, `connector_id`, `tariff`, `prices_incl_vat`,
`end_user_total_cost_incl_vat`, `currency`, `last_updated` are plain `snake_case` with no vendor
prefix. OCPI 2.3.0 advises against prefixing extension fields (`x-`, `custom`), so these names
remain valid if a connection later moves to a newer OCPI version.

OCPI 2.2.1 advises prefixing custom module IDs with a party identifier (for example
`nltnm-tokens`). This extension deliberately does not: it is meant to be implemented by any CPO
and eMSP, and a party prefix would tie it to one company. `end_user_pricing` is a candidate name
for standardisation.

---

## 8. Implementation checklist (eMSP)

- [ ] Agree with the CPO that the extension is enabled for the connection, on the request
      timeouts the CPO will apply, and on the session-push cadence.
- [ ] Expose `end_user_pricing` in the version-details endpoint list, or share the URL out of
      band.
- [ ] Keep your copy of the CPO's Locations complete for connections where the extension is
      enabled: a Location you do not know gets no tariff.
- [ ] Decide, per contract type, whether drivers are priced live. Return `NOT_AVAILABLE` at
      tariff time for those who are not.
- [ ] Implement `GET …/tariffs/{country_code}/{party_id}/{location_id}[/{evse_uid}[/{connector_id}]]`:
      resolve the driver's tariff per connector for the token, VAT-inclusive prices with
      `prices_incl_vat: true`, within the agreed timeout, omit connectors you cannot price.
- [ ] Implement `GET …/session_costs/{country_code}/{party_id}/{session_id}`: return the current
      cumulative driver cost as `end_user_total_cost_incl_vat`, with the time it was computed as
      `last_updated`, answer within the agreed timeout, `PENDING` when not priceable yet, and the
      session `tariff` (with `prices_incl_vat: true`) when it differs from the §3 one.
- [ ] Never let pricing failures surface as anything other than `PENDING`, `NOT_AVAILABLE` or a
      non-`1000` status on these two endpoints.
