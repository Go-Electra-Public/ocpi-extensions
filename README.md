# Electra OCPI extensions

Open specifications for custom [OCPI](https://evroaming.org/ocpi/) extensions, published by
Electra and meant to be implemented by any CPO and eMSP.

OCPI covers the CPO ↔ eMSP contract well, but leaves gaps that are visible to the driver
standing in front of a charge point. Rather than solving those gaps with private, undocumented
behaviour per partner, we publish them here so any party can implement them from a single
source of truth.

Each extension is **additive and optional**: it never changes a standard OCPI message, and a
partner that does not implement it is unaffected. Where an extension needs a new exchange, it
adds a custom module, enabled per connection by agreement.

## Extensions

| Extension | Status | Versions | Spec |
| --- | --- | --- | --- |
| End-user pricing display | Draft, under review | OCPI 2.1.1, 2.2.1 | [`extensions/end-user-pricing`](extensions/end-user-pricing) |

## How these specs are written

- **One document per extension and OCPI version.** The wire shapes differ between 2.1.1 and
  2.2.1, so each version gets its own normative document instead of a single document full of
  conditionals.
- **Normative language** follows [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119)
  (MUST / SHOULD / MAY).
- **JSON Schema** (draft 2020-12) definitions under `schemas/` are the machine-readable
  companion to the prose. Where the two disagree, the prose wins and the schema is a bug.
- **Examples** under `examples/` are non-normative but are expected to validate against the
  schemas.

## Naming conventions

Extension modules and fields use plain `snake_case` names with no vendor prefix (no `x-`, no
`electra_`, no `custom_`). This follows the OCPI 2.3.0 guidance on extension fields, and keeps
the door open for an extension to be adopted upstream unchanged.

## Enabling an extension

Extensions are enabled **per connection**, by agreement, and configured manually on both sides.
There is no protocol negotiation and no capability discovery beyond a custom module appearing
in the version-details endpoint list of the party that hosts it.

To discuss enabling an extension on a connection with Electra, contact your Electra roaming
counterpart.

## Contributing

Feedback from implementers is the point of publishing these. Open an issue with the OCPI
version you target, the message or endpoint involved, and what is ambiguous or unimplementable.
Specs are drafts until validated; each document gets a changelog from its first validated
version (v1.0).

## License

Copyright © 2026 Electra.

These specifications are licensed under the
[Creative Commons Attribution 4.0 International](LICENSE) license (CC BY 4.0). You may
copy, quote, adapt and redistribute them, including commercially, as long as you give
appropriate credit.
