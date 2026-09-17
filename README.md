# Electra OCPI extensions

Open specifications for the custom [OCPI](https://evroaming.org/ocpi/) extensions that
Electra, as a CPO, supports on its roaming connections.

OCPI covers the CPO ↔ eMSP contract well, but leaves gaps that are visible to the driver
standing in front of a charge point. Rather than solving those gaps with private, undocumented
behaviour per partner, we publish them here so any eMSP can implement them from a single
source of truth.

Each extension is **purely additive and optional**: it rides on OCPI messages that already
exist, adds only optional fields, and a partner that does not implement it is unaffected.
Per OCPI's own rules, a receiver must ignore fields it does not know.

## Extensions

| Extension | Status | Versions | Spec |
| --- | --- | --- | --- |
| End-user pricing display | Draft (v1) | OCPI 2.1.1, 2.2.1 | [`extensions/end-user-pricing`](extensions/end-user-pricing) |

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

Extension fields use plain `snake_case` names with no vendor prefix (no `x-`, no `electra_`,
no `custom_`). This follows the OCPI 2.3.0 guidance on extension fields, and keeps the door
open for a field to be adopted upstream unchanged.

## Enabling an extension

Extensions are enabled **per connection**, by agreement, and configured manually on both
sides. There is no protocol negotiation, no capability discovery and no new endpoint: if the
extension is enabled for a connection, we read the optional fields when they are present and
fall back to standard OCPI behaviour when they are not.

To discuss enabling an extension on your connection, contact your Electra roaming
counterpart.

## Contributing

Feedback from implementers is the point of publishing these. Open an issue with the OCPI
version you target, the message involved, and what is ambiguous or unimplementable. Spec
changes are versioned in the "Changelog" section of each document.

## License

Copyright © 2026 Electra.

These specifications are licensed under the
[Creative Commons Attribution 4.0 International](LICENSE) license (CC BY 4.0). You may
copy, quote, adapt and redistribute them, including commercially, as long as you give
appropriate credit.
