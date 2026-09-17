# End-user pricing display — OCPI 2.2.1

**Status:** Draft — v1
**Direction:** eMSP → CPO
**Applies to:** OCPI 2.2.1 (and 2.2) connections
**Other versions:** [OCPI 2.1.1](ocpi-2.1.1.md)

The key words MUST, MUST NOT, SHOULD, SHOULD NOT and MAY are to be interpreted as described in
[RFC 2119](https://www.rfc-editor.org/rfc/rfc2119).

Read [`README.md`](README.md) first for the rationale, the design principles and the cost
semantics. This document is the normative wire contract.

---

## 1. Overview

The extension adds three optional fields, all sent by the **eMSP** in **response bodies** of
messages the CPO already sends:

| # | Field | Type | Carried on |
| --- | --- | --- | --- |
| 1 | `end_user_tariff` | OCPI 2.2.1 `Tariff` | `AuthorizationInfo` — response to `POST /tokens/{token_uid}/authorize` |
| 2 | `end_user_tariff` | OCPI 2.2.1 `Tariff` | response envelope `data` of `PUT`/`PATCH /sessions/{session_id}` (fallback, §3) |
| 3 | `end_user_total_cost` | OCPI 2.2.1 `Price` | response envelope `data` of `PUT`/`PATCH /sessions/{session_id}` |
| 4 | `currency` | `CiString(3)` | response envelope `data`, alongside `end_user_total_cost` |

No request the CPO sends is modified. No endpoint is added on either side.

A receiver MUST ignore fields it does not recognise (OCPI 2.2.1, §4.2). An eMSP that does not
implement this extension therefore needs to change nothing, and a CPO that does not implement
it will ignore these fields.

---

## 2. End-user tariff on real-time authorization

### 2.1 Message

`POST /tokens/{token_uid}/authorize` (Tokens module, CPO → eMSP, `Real-Time` authorization).

The eMSP MAY add an optional `end_user_tariff` field to the `AuthorizationInfo` object it
returns in `data`.

| Field | Type | Card. | Description |
| --- | --- | --- | --- |
| `end_user_tariff` | `Tariff` | ? | The tariff the eMSP applies to this driver, for this token, at this location. |

`Tariff` is the standard OCPI 2.2.1 `Tariff` object, unchanged.

### 2.2 Example

```json
{
  "data": {
    "allowed": "ALLOWED",
    "token": {
      "country_code": "FR",
      "party_id": "CMP",
      "uid": "12345678",
      "type": "RFID",
      "contract_id": "FR-CMP-C12345678-X",
      "issuer": "Example Mobility",
      "valid": true,
      "whitelist": "NEVER",
      "last_updated": "2026-09-17T09:00:00Z"
    },
    "authorization_reference": "a1b2c3d4-0000-4000-8000-000000000001",
    "end_user_tariff": {
      "country_code": "FR",
      "party_id": "CMP",
      "id": "cmp-elc-dc-2026-09",
      "currency": "EUR",
      "type": "REGULAR",
      "elements": [
        {
          "price_components": [
            { "type": "ENERGY", "price": 0.49, "vat": 20.0, "step_size": 1 }
          ]
        },
        {
          "price_components": [
            { "type": "PARKING_TIME", "price": 6.0, "vat": 20.0, "step_size": 60 }
          ],
          "restrictions": { "min_duration": 1800 }
        }
      ],
      "last_updated": "2026-09-17T09:00:00Z"
    }
  },
  "status_code": 1000,
  "status_message": "Success",
  "timestamp": "2026-09-17T09:12:00Z"
}
```

### 2.3 Why this message

The authorization request is the moment the driver taps their card and before they plug in — it
is exactly when the charge point expects the CPO to push `SetUserPrice`. A tariff delivered here
answers the question the driver is actually asking: *what will this cost me?*

### 2.4 Requirements

- The tariff MUST be the price the **eMSP bills the driver**, not the CPO's price to the eMSP.
- `currency` inside the `Tariff` object MUST be the currency the eMSP bills the driver in.
- `price` values in `price_components` are **excluding VAT**, with `vat` given as a percentage,
  per standard OCPI 2.2.1 semantics. The CPO computes the VAT-inclusive figure for display.
- The eMSP SHOULD include `vat` on every price component. When `vat` is absent the CPO MUST
  display the excluding-VAT amount without inventing a rate, which is likely to understate the
  price to the driver.
- `end_user_tariff` MUST be omitted rather than sent empty or with placeholder values when the
  eMSP cannot resolve a price. A `Tariff` with no `elements` MUST NOT be sent.
- Sending `end_user_tariff` when `allowed` is not `ALLOWED` is pointless; the eMSP SHOULD omit
  it. A CPO MUST ignore it in that case.
- The tariff MUST be self-contained. `Tariff.id` is opaque to the CPO: the CPO does not look it
  up, cache it across sessions, or fetch it from any endpoint.

### 2.5 Limitation

Tokens with `whitelist` set to `ALWAYS` or `ALLOWED_OFFLINE`, and sessions started remotely with
`START_SESSION`, never produce an authorization request. For those flows there is no 2.x
carrier; see §3.

---

## 3. End-user tariff on the session push response (limited fallback)

The eMSP MAY also return `end_user_tariff` in the `data` of its response to a
`PUT`/`PATCH /sessions/{session_id}` (§4).

### 3.1 Timing limitation

The CPO's OCPI session is created when the charge point reports the transaction has started, not
at authorization. Electra does not use the `PENDING` session status. Therefore anything carried
on the first session message arrives **after the driver has plugged in and charging has begun**.

| Step | OCPP | OCPI | Screen |
| --- | --- | --- | --- |
| Card tap | `Authorize` | `POST /tokens/{uid}/authorize` → `end_user_tariff` (§2) | `SetUserPrice`, **before plugging in** |
| Plug in and start | `StartTransaction` | session created `ACTIVE`, first `PUT /sessions` → response `data` (§3) | anything here shows **after charging has started** |
| Charging | `MeterValues` | `PUT /sessions` → `end_user_total_cost` | `RunningCost` |
| Stop | `StopTransaction` | final `PUT` (`COMPLETED`) → `end_user_total_cost` | `FinalCost` |

> **§2 is the tariff carrier. §3 is not a substitute for it.** A tariff that first appears with
> the session messages is too late for the purpose of telling the driver what they are about to
> commit to.

### 3.2 Where §3 is useful

- **Tariff change mid-session** — the eMSP moves to a different tariff element (time-of-day
  boundary, parking fee starting) and wants the displayed tariff refreshed alongside the running
  cost. After authorization this is the only channel.
- **Whitelisted and `ALLOWED_OFFLINE` tokens** — no authorization request exists, so this is the
  only option. The result is a late display rather than none.
- **Authorization answered without a tariff** — the eMSP supports the extension but could not
  resolve the price in time (for example contract resolution is asynchronous on its side) and
  completes later.

### 3.3 Where §3 brings nothing

- **Remote start (`START_SESSION`)** — the driver selected the station in the eMSP's app, which
  already displayed the price. The pre-charge screen adds little; the running cost (§4) is what
  matters.
- **Card tap with real-time authorization** — §2 already delivered the tariff. Repeating an
  unchanged tariff is harmless and the CPO MAY ignore it.

### 3.4 Requirements

- All requirements in §2.4 apply unchanged.
- The eMSP SHOULD send `end_user_tariff` here only when it has changed since the last value sent
  for this session, or when §2 could not carry it.
- When a tariff is sent on a session message, it MUST be the tariff in force **from that point
  onward**. This extension has no way to express a retroactive tariff correction, and the CPO
  MUST NOT attempt to reconstruct one.

---

## 4. Running end-user total cost

### 4.1 Message

`PUT /sessions/{session_id}` and `PATCH /sessions/{session_id}` (Sessions module, CPO → eMSP).

The request is unchanged. The eMSP puts the extension fields in the — normally empty — `data`
member of the OCPI response envelope.

| Field | Type | Card. | Description |
| --- | --- | --- | --- |
| `end_user_total_cost` | `Price` | ? | Cumulative cost of the session to the driver, reflecting the session state in the request being answered. |
| `currency` | `CiString(3)` | ? | ISO 4217 code of the currency of `end_user_total_cost`. REQUIRED when `end_user_total_cost` is present. |
| `end_user_tariff` | `Tariff` | ? | See §3. |

`Price` is the standard OCPI 2.2.1 object: `{ "excl_vat": number, "incl_vat": number }`.

### 4.2 Example

```json
{
  "data": {
    "end_user_total_cost": { "excl_vat": 4.10, "incl_vat": 4.92 },
    "currency": "EUR"
  },
  "status_code": 1000,
  "status_message": "Success",
  "timestamp": "2026-09-17T09:12:03Z"
}
```

With a mid-session tariff change:

```json
{
  "data": {
    "end_user_tariff": {
      "country_code": "FR",
      "party_id": "CMP",
      "id": "cmp-elc-dc-2026-09-peak",
      "currency": "EUR",
      "type": "REGULAR",
      "elements": [
        {
          "price_components": [
            { "type": "ENERGY", "price": 0.59, "vat": 20.0, "step_size": 1 }
          ]
        }
      ],
      "last_updated": "2026-09-17T10:00:00Z"
    },
    "end_user_total_cost": { "excl_vat": 12.40, "incl_vat": 14.88 },
    "currency": "EUR"
  },
  "status_code": 1000,
  "status_message": "Success",
  "timestamp": "2026-09-17T10:00:02Z"
}
```

### 4.3 Semantics

- **Cumulative.** `end_user_total_cost` is the total for the session so far, not a delta since
  the previous message.
- **Tied to the request it answers.** The value MUST reflect the session state in the request
  being answered — its energy and its timestamps. There is deliberately no separate
  "computed at" timestamp: the CPO pairs the value with the meter reading it just pushed. This
  is why an eMSP MUST NOT answer with a cost computed from a later or an earlier state of the
  session.
- **VAT.** Both `excl_vat` and `incl_vat` SHOULD be provided. The CPO displays the
  VAT-inclusive figure, since that is what the driver pays. If only `excl_vat` is present the
  CPO MUST display it as-is without applying a VAT rate of its own.
- **Currency.** In the currency the eMSP bills the driver in. The CPO performs no conversion.
- **Final value.** On the message where the session status is `COMPLETED`, the value is treated
  as the **provisional final cost** and rendered as `FinalCost`. It is informational: the eMSP's
  invoice to the driver prevails.
- **Absent field.** No `end_user_total_cost` means the eMSP does not provide one for this
  session. The CPO falls back to its default behaviour, which is to show no roaming cost on the
  screen.
- **Monotonicity.** Values SHOULD be non-decreasing over the life of a session. A value lower
  than one previously sent will be displayed as-is, which is confusing to the driver; the CPO
  MAY ignore a decrease.
- **Unrelated to the CDR.** See "Cost semantics" in [`README.md`](README.md).

### 4.4 Non-blocking

Producing `end_user_total_cost` MUST NOT delay the response. If the eMSP cannot price the
session in time it MUST answer `status_code` `1000` with the field omitted rather than answer
late or with an error. An eMSP SHOULD keep its session-push response within the CPO's normal
OCPI timeout.

An error `status_code` in the response is handled per standard OCPI and any extension fields in
`data` are ignored.

---

## 5. Rendering

The CPO builds all screen text. This section states what an eMSP can and cannot expect to see
displayed, so that a tariff can be authored with the screen in mind.

- **Supported price component types.** `ENERGY`, `PARKING_TIME`, `TIME` and `FLAT`. These are the
  four `TariffDimensionType` values, so no component type is structurally unsupported — but a
  tariff built mostly from `FLAT` and `TIME` components renders as a longer, less readable
  string than an energy-based one.
- **Restrictions.** Simple restrictions that map to a threshold the CPO can state — notably
  `min_duration` on a parking component — are rendered. Complex combinations of restrictions may
  not be, in which case the CPO renders the components it can and marks the rest as not
  displayed.
- **Partial rendering, never free text.** When part of a tariff cannot be rendered, the CPO
  displays what it can and records the outcome. It MUST NOT fall back to any eMSP-provided
  string.
- **`tariff_alt_text` is ignored**, as is `tariff_alt_url`. Do not use them to get a message onto
  the screen.
- **`min_price` / `max_price`** on a tariff are not rendered in v1.
- **Locale.** The screen is rendered in the station's locale, not the driver's.
- **Refresh rate.** The screen's running-cost refresh is bounded by the CPO's session-push
  cadence for the connection, which is throttled (60 seconds by default and higher on some
  partners). Sub-minute cost updates are not achievable through this extension. For an opted-in
  connection, a session-push delay of 60 seconds or less is recommended.

---

## 6. Field naming

`end_user_tariff`, `end_user_total_cost` and `currency` are plain `snake_case` with no vendor
prefix. OCPI 2.3.0 both requires receivers not to reject payloads containing undocumented
fields and advises against prefixing extension fields (`x-`, `custom`), so these names remain
valid if a connection later moves to 2.3.0.

---

## 7. Implementation checklist (eMSP)

- [ ] Agree with Electra that the extension is enabled for the connection.
- [ ] Add `end_user_tariff` to the `AuthorizationInfo` returned by
      `POST /tokens/{token_uid}/authorize`, resolved for the token and the location.
- [ ] Add `end_user_total_cost` and `currency` to the `data` of the `PUT`/`PATCH /sessions`
      response, recomputed from the session state in each request.
- [ ] Ensure pricing never delays or fails these responses (§4.4).
- [ ] Optionally send `end_user_tariff` on session responses for the fallback cases in §3.2.
- [ ] Validate payloads against [`schemas/2.2.1/`](schemas/2.2.1).

---

## 8. Changelog

| Version | Date | Changes |
| --- | --- | --- |
| v1 draft | 2026-09-17 | Initial published draft. |
