# End-user pricing display

> **In one sentence:** the eMSP tells the CPO, over OCPI messages it already answers, what the
> driver pays (`end_user_tariff`) and what the session currently costs them
> (`end_user_total_cost`); the CPO renders both on the charge-point screen.

| | |
| --- | --- |
| Status | Draft — v1 |
| OCPI versions | [2.1.1](ocpi-2.1.1.md) · [2.2.1](ocpi-2.2.1.md) |
| Direction | eMSP → CPO |
| New endpoints | none |
| New modules | none |
| Modified messages | `POST /tokens/{token_uid}/authorize` (response), `PUT`/`PATCH /sessions/{session_id}` (response) |

## Why

As a CPO, Electra displays pricing on the charge-point screen using OCPP 1.6 California
Pricing: `SetUserPrice` before the session starts, `RunningCost` during it, `FinalCost` at the
end.

For a driver charging with their own card or through the Electra app, we know the price and the
screen is correct. For a **roaming** driver, we do not: the price they will be billed is set by
their eMSP, and OCPI gives the eMSP no way to tell us about it.

- The `Tariffs` module flows **CPO → eMSP** only. It carries our price to the eMSP, not the
  eMSP's price to the driver.
- `Session.total_cost` and the CDR are the **CPO ↔ eMSP** B2B amounts. They are not what the
  driver pays.

So the screen either shows nothing, or shows our ad-hoc price — which is not what the roaming
driver will be charged. Both are bad: the first is a blank screen at the moment the driver
decides whether to plug in, the second is actively misleading.

This extension closes that gap with three optional fields.

## What it adds

| Field | Carried on | Purpose | Screen |
| --- | --- | --- | --- |
| `end_user_tariff` | `AuthorizationInfo` in the `POST /tokens/{token_uid}/authorize` response | the tariff the eMSP applies to this driver at this station | `SetUserPrice`, before the driver plugs in |
| `end_user_total_cost` | `data` of the CPO's `PUT`/`PATCH /sessions/{session_id}` response | cumulative cost of the session to the driver so far | `RunningCost` during the session, `FinalCost` at the end |
| `currency` | alongside `end_user_total_cost` | ISO 4217 currency of the amounts | — |

`end_user_tariff` may also be repeated in the session-push response, as a **limited fallback**
for the cases where no authorization request happens or where the tariff changes mid-session.
See "Session push response" in the version documents.

## Design principles

These explain most of the "why is it like that" questions, so they are worth reading before the
normative text.

**Reuse OCPI objects, do not invent shapes.**
The end-user tariff is an OCPI `Tariff` object of the negotiated version. The running cost is an
OCPI `Price` in 2.2.1, and a number plus a currency in 2.1.1. An implementer already has the
serialisers.

**The CPO renders; the eMSP sends structured data.**
The eMSP sends price components only. The CPO builds the screen text — wording, formatting,
rounding, and translation into the station's locale — exactly as it does for its own tariffs.
Charge-point screens have hard constraints on length and layout that the eMSP cannot know, and
a partner-supplied string would bypass all of them. Consequently `Tariff.tariff_alt_text` is
**ignored for rendering**; do not rely on it to get a message onto the screen.

**Purely additive and optional.**
No new module, no new endpoint, no change to any request the CPO sends. A non-implementing eMSP
answers exactly as it does today and nothing breaks.

**Carried on response bodies.**
Everything rides on messages the eMSP already answers. There is nothing new for the eMSP to
expose, host, or authenticate.

**Per-connection opt-in, no negotiation.**
Enabled by agreement and configured manually on both sides. No capability discovery.

**Minimal.**
Three fields. Anything else waits for a concrete partner need.

## Cost semantics, in one place

Two amounts exist in a roaming session and they are unrelated:

| Amount | Between | Where |
| --- | --- | --- |
| `Session.total_cost`, CDR `total_cost` | CPO ↔ eMSP | standard OCPI |
| `end_user_total_cost` | eMSP ↔ driver | this extension |

`end_user_total_cost` is **informational**. It exists to show the driver a plausible running
figure on the screen. The eMSP's own invoice to the driver prevails, and this extension creates
no settlement obligation in either direction. In particular, it does not affect the CDR.

## Scope

**In scope for v1:** direct OCPI 2.1.1 and 2.2.1 connections between an eMSP and Electra as CPO.

**Out of scope for v1:**

- **Hubs.** Direct connections only. Hub-mediated connections often validate payloads strictly
  and may strip unknown fields, so we make no claim about them yet.
- **OICP / Hubject.** Different protocol, not covered.
- **Currency conversion.** The eMSP sends amounts in the currency it bills the driver in and we
  display them as-is.
- **Reconciliation.** Nothing here is used for invoicing or dispute handling.

## Legal note

AFIR price transparency obligations bear on the CPO's own ad-hoc price, which we display
independently of this extension. An `end_user_total_cost` shown on the screen is presented as
the eMSP's informational price and remains the eMSP's responsibility.

## Where to start

- eMSP on OCPI 2.2.1 → [`ocpi-2.2.1.md`](ocpi-2.2.1.md)
- eMSP on OCPI 2.1.1 → [`ocpi-2.1.1.md`](ocpi-2.1.1.md)
- Machine-readable definitions → [`schemas/`](schemas)
- Copy-pasteable payloads → [`examples/`](examples)
