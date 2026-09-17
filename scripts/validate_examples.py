#!/usr/bin/env python3
"""Validate every example payload against its extension JSON Schema.

Examples are non-normative, but a broken example is worse than no example, so CI
checks them. Mapping is by filename prefix: `authorize-*` validates against
authorization-info.schema.json wrapped in the OCPI response envelope,
`session-*` against session-push-response.schema.json.

Usage: python3 scripts/validate_examples.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parent.parent
EXTENSIONS = ROOT / "extensions"


def registry_for(schema_dir: Path) -> Registry:
    """Resolve `$ref`s like "tariff.schema.json" against sibling files on disk."""
    registry = Registry()
    for path in sorted(schema_dir.glob("*.schema.json")):
        schema = json.loads(path.read_text())
        resource = Resource.from_contents(schema)
        registry = registry.with_resource(uri=path.name, resource=resource)
        if "$id" in schema:
            registry = registry.with_resource(uri=schema["$id"], resource=resource)
    return registry


def schema_for(example: Path) -> str | None:
    name = example.name
    if name.startswith("authorize-"):
        return "authorization-info.schema.json"
    if name.startswith("session-"):
        return "session-push-response.schema.json"
    return None


def validate(example: Path, schema_dir: Path) -> list[str]:
    schema_name = schema_for(example)
    if schema_name is None:
        return [f"no schema mapping for {example.name}"]

    schema_path = schema_dir / schema_name
    payload = json.loads(example.read_text())
    registry = registry_for(schema_dir)
    validator = Draft202012Validator(
        json.loads(schema_path.read_text()), registry=registry
    )

    # An authorize example is a full OCPI envelope; the schema describes its `data`.
    target = payload["data"] if schema_name == "authorization-info.schema.json" else payload

    return [
        f"{'/'.join(str(p) for p in error.absolute_path) or '<root>'}: {error.message}"
        for error in validator.iter_errors(target)
    ]


def main() -> int:
    failures = 0
    checked = 0

    for examples_dir in sorted(EXTENSIONS.glob("*/examples/*")):
        version = examples_dir.name
        schema_dir = examples_dir.parent.parent / "schemas" / version
        if not schema_dir.is_dir():
            print(f"FAIL {examples_dir}: no schemas/{version} directory")
            failures += 1
            continue

        for example in sorted(examples_dir.glob("*.json")):
            checked += 1
            errors = validate(example, schema_dir)
            rel = example.relative_to(ROOT)
            if errors:
                failures += 1
                print(f"FAIL {rel}")
                for error in errors:
                    print(f"  {error}")
            else:
                print(f"ok   {rel}")

    print(f"\n{checked} example(s) checked, {failures} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
