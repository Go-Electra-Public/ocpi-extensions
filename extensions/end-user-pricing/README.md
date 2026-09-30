# End-user pricing display

> **In one sentence:** the CPO asks the eMSP, through a small dedicated module, what the driver
> pays at a given Location, EVSE or connector (`tariffs`) and what a given session currently
> costs them (`session_costs`); the CPO shows both to the driver, on the charge-point screen or
> through other channels.

| | |
| --- | --- |
| Status | Draft, under review, not ready for implementation |
| OCPI versions | [2.1.1](ocpi-2.1.1.md) · [2.2.1](ocpi-2.2.1.md) |
| Direction | CPO → eMSP requests; eMSP answers (the eMSP is the **sender** of the data) |
| New module | `end_user_pricing`, hosted by the eMSP, two GET endpoints |
| Modified messages | none |

## Why

A CPO can display pricing on the charge-point screen, for example with OCPP 1.6 California
Pricing: `SetUserPrice` before the session starts, `RunningCost` during it, `FinalCost` at the
end.

For a driver who pays the CPO directly (ad-hoc payment, the CPO's own app), the CPO knows the
price and the screen is correct. For a **roaming** driver, it does not: the price they will be
billed is set by their eMSP, and OCPI gives the eMSP no way to tell the CPO about it.

- The `Tariffs` module flows **CPO → eMSP** only. It carries the CPO's price to the eMSP, not the
  eMSP's price to the driver.
- `Session.total_cost` and the CDR are the **CPO ↔ eMSP** B2B amounts. They are not what the
  driver pays.

So the screen either shows nothing, or shows the CPO's ad-hoc price — which is not what the
roaming driver will be charged. Both are bad: the first is a blank screen at the moment the
driver decides whether to plug in, the second is actively misleading.

This extension closes that gap with one small module on the eMSP side.

## What it adds

One module, `end_user_pricing`, exposed by the eMSP and called by the CPO. It has two endpoints:

| Endpoint | Input | Output | When the CPO calls it | Driver sees |
| --- | --- | --- | --- | --- |
| `GET …/tariffs/{country_code}/{party_id}/{location_id}[/{evse_uid}[/{connector_id}]]` | a token (uid and type) and a Location, optionally narrowed to one EVSE or connector | a `pricing_status` and one OCPI `Tariff` per connector the eMSP can price | when the token is presented (after a successful authorization, or directly for whitelisted tokens), and optionally on remote start | their tariff, before plugging in |
| `GET …/session_costs/{country_code}/{party_id}/{session_id}` | a session the CPO has already pushed | a `pricing_status` and, when available, the cumulative cost of the session to the driver, its currency, the time the eMSP computed it, and optionally the tariff now applied to the session | once after each session push the eMSP has acknowledged | the running cost during the session, the provisional final cost at the end, and the updated tariff if it changed (for example after a promotion) |

## Why pull rather than fields in existing responses

An earlier draft carried the tariff in the `AuthorizationInfo` returned to
`POST /tokens/{token_uid}/authorize`, and the running cost in the `data` of the
`PUT`/`PATCH /sessions` response. Review with the eMSP side showed that this couples two
concerns that are separate in an eMSP architecture: **authorizing** a token and **pricing** it
for the driver are different services with different latencies, and the same is true of
**ingesting** a session update and **pricing** the session. Answering an authorization or a
session push with pricing data forces the eMSP to compute a price synchronously inside a flow
that must stay fast.

The pull model decouples them:

- The eMSP answers `authorize` and `sessions` exactly as today. Nothing about existing flows
  changes, on either side.
- Pricing runs in its own request with its own latency budget, and can be served from whatever
  state the eMSP has already computed.

It also removes the earlier draft's biggest functional gap: tokens whitelisted `ALWAYS` or
`ALLOWED_OFFLINE`, and remote starts, produce no `authorize` call, so that draft had no way to
show them a tariff before plug-in. With a dedicated endpoint the CPO asks whenever it needs.

The cost is one more module for the eMSP to host under its existing OCPI credentials, and
roughly one additional request per session update from the CPO.

Not every driver is priced live. A B2B fleet billed monthly with volume discounts, or a
post-paid subscription, has no meaningful running cost during the session. Both endpoints
therefore return a `pricing_status` (`AVAILABLE`, `PENDING`, `NOT_AVAILABLE`), so an eMSP can
say at tariff time that a token will not be priced live and the CPO does not poll for that
session at all.

## Design principles

These explain most of the "why is it like that" questions, so they are worth reading before the
normative text.

**The eMSP is the source of truth for the driver's price.**
It sets the tariff, computes the cost, and bills the driver. The CPO only consumes what the eMSP
returns and displays it. It does not compute, correct, complete or reconcile a driver-facing
price on its own; the only exception is applying the VAT rate carried by an OCPI 2.2.1 tariff.
It holds no data of its own about the driver's price beyond what it received for the current
session.

**Reuse OCPI objects, do not invent shapes.**
The end-user tariff is an OCPI `Tariff` object of the negotiated version. The running cost is an
OCPI `Price` in 2.2.1, and a number plus a currency in 2.1.1. An implementer already has the
serialisers.

**The CPO renders; the eMSP sends structured data.**
The eMSP sends price components only. The CPO builds the text shown to the driver — wording,
formatting, rounding, and translation into the station's locale — exactly as it does for its
own tariffs. Charge-point screens have hard constraints on length and layout that the eMSP
cannot know. How the CPO renders the objects it receives is at its discretion and outside this
specification.

**Pull, not push. The CPO asks, the eMSP answers from state it already has.**
No pricing data is ever expected inside an existing OCPI response. The eMSP never has to compute
a price inside the authorization or session-ingestion path.

**No change to existing modules.**
`Tokens`, `Sessions`, `CDRs`, `Tariffs`, `Locations` and `Commands` are used exactly as the
standard defines them. The extension is one additional module, discoverable through the
standard version-details endpoint list.

**Per-connection opt-in, no negotiation.**
Enabled by agreement and configured manually on both sides. No capability discovery beyond the
module appearing in the eMSP's endpoint list.

**Non-blocking and best-effort on both sides.**
A missing, late or errored pricing answer degrades to "no roaming price shown". It never affects
authorization, the session, or the CDR. The price may change after the session starts; the eMSP
makes a best effort to return what it will bill, the CPO a best effort to display it, and the
eMSP's invoice to the driver is the only reference for billing.

**Minimal.**
Two endpoints. Anything else waits for a concrete partner need.

## Cost semantics, in one place

Two amounts exist in a roaming session and they are unrelated:

| Amount | Between | Where |
| --- | --- | --- |
| `Session.total_cost`, CDR `total_cost` | CPO ↔ eMSP | standard OCPI |
| `end_user_total_cost` (2.2.1) / `end_user_total_cost_incl_vat` (2.1.1), session cost endpoint | eMSP ↔ driver | this extension |

The end-user cost is **informational**. It exists to show the driver a plausible running figure.
The eMSP's own invoice to the driver prevails, and this extension creates no settlement
obligation in either direction. In particular, it does not affect the CDR.

Because the cost is pulled rather than returned with the session push, it is not tied to a
specific request. The eMSP states **when it computed the figure** (`last_updated`, on its own
clock) and the CPO uses that only for freshness. How the eMSP derives the cost, from the CPO's
session updates or from inputs of its own such as promotions or credits, is not constrained by
the extension.

## Scope

**In scope:** direct OCPI 2.1.1 and 2.2.1 connections between an eMSP and a CPO.

**Out of scope:**

- **Hubs.** Direct connections only. A hub would need to route a custom module; we make no claim
  about that yet.
- **OICP / Hubject.** Different protocol, not covered.
- **Currency conversion.** The eMSP sends amounts in the currency it bills the driver in and the
  CPO displays them as-is.
- **Reconciliation.** Nothing here is used for invoicing or dispute handling.
- **Sub-minute running cost.** The CPO polls at most once per session push it sends; the push
  cadence bounds the refresh rate.

## Legal note

AFIR price transparency obligations bear on the CPO's own ad-hoc price, which the CPO displays
independently of this extension. Prices and costs shown through this extension are presented as
the eMSP's indicative price and remain the eMSP's responsibility.

## Where to start

- eMSP on OCPI 2.2.1 → [`ocpi-2.2.1.md`](ocpi-2.2.1.md)
- eMSP on OCPI 2.1.1 → [`ocpi-2.1.1.md`](ocpi-2.1.1.md)
- Machine-readable definitions → [`schemas/`](schemas)
- Copy-pasteable payloads → [`examples/`](examples)
