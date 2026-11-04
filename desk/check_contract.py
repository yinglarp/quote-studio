#!/usr/bin/env python3
"""Check one Enquiry Desk pack file against its contract schema in design/schemas/.

Run from the project folder:

    python desk/check_contract.py desk/packs/enq-03/event.json
    python desk/check_contract.py some-copy.json --schema design/schemas/event.schema.json

The schema is picked from the file name: event.json -> design/schemas/event.schema.json.
Prints PASS, or FAIL and one line per field that is missing or wrong.
Exit code 0 = PASS, 1 = FAIL, 2 = the file or schema could not be read.

Python standard library only. It understands the parts of JSON Schema the Desk schemas use:
type, const, enum, pattern, minLength/maxLength, minimum/maximum, minItems/maxItems, required,
properties, additionalProperties, items, allOf, if/then and not.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMAS = ROOT / "design" / "schemas"
TYPES = {
    "null": lambda v: v is None,
    "boolean": lambda v: isinstance(v, bool),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "string": lambda v: isinstance(v, str),
    "array": lambda v: isinstance(v, list),
    "object": lambda v: isinstance(v, dict),
}


def type_name(v):
    return next(t for t in ("null", "boolean", "integer", "number", "string", "array", "object") if TYPES[t](v))


def show(v):
    s = json.dumps(v, ensure_ascii=False)
    return s if len(s) <= 40 else s[:37] + "..."


def at(path, key):
    if isinstance(key, int):
        return f"{path}[{key}]"
    return f"{path}.{key}" if path else key


def because(cond):
    """'because status is "full"' for an if-clause, so a then-error says why it applies."""
    for k, s in cond.get("properties", {}).items():
        if "const" in s:
            return f' (because {k} is {show(s["const"])})'
        if "enum" in s:
            return f' (because {k} is one of {", ".join(show(e) for e in s["enum"])})'
        if "minItems" in s:
            return f" (because {k} is not empty)"
    return ""


def check(value, schema, path, errors):
    """Append one plain-language line per problem to errors."""
    where = path or "(file)"
    if "type" in schema:
        allowed = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(TYPES[t](value) for t in allowed):
            got = "null" if value is None else f"{type_name(value)} {show(value)}"
            errors.append(f"{where}: wrong type: expected {' or '.join(allowed)}, got {got}")
            return
    if "const" in schema and value != schema["const"]:
        errors.append(f"{where}: wrong value: must be {show(schema['const'])}, got {show(value)}")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{where}: wrong value: must be one of {', '.join(show(e) for e in schema['enum'])}; got {show(value)}")

    if isinstance(value, str):
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errors.append(f"{where}: wrong format: {show(value)} does not match {schema['pattern']}")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            errors.append(f"{where}: too long: {len(value)} characters, the limit is {schema['maxLength']} (keep it a short phrase)")
        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append(f"{where}: too short: at least {schema['minLength']} characters")
    if TYPES["number"](value):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{where}: too small: {value} is below {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{where}: too large: {value} is above {schema['maximum']}")
    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append(f"{where}: too few items: {len(value)}, need at least {schema['minItems']}")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            errors.append(f"{where}: too many items: {len(value)}, at most {schema['maxItems']}")
        if "items" in schema:
            for i, item in enumerate(value):
                check(item, schema["items"], at(path, i), errors)
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{at(path, key)}: missing")
        props = schema.get("properties", {})
        for key, sub in props.items():
            if key in value:
                check(value[key], sub, at(path, key), errors)
        extra = schema.get("additionalProperties", True)
        for key in value:
            if key in props:
                continue
            if extra is False:
                errors.append(f"{at(path, key)}: not in the contract")
            elif isinstance(extra, dict):
                check(value[key], extra, at(path, key), errors)

    for sub in schema.get("allOf", []):
        check(value, sub, path, errors)
    if "if" in schema:
        probe = []
        check(value, schema["if"], path, probe)
        if not probe and "then" in schema:
            found = []
            check(value, schema["then"], path, found)
            errors.extend(e + because(schema["if"]) for e in found)
    if "not" in schema:
        probe = []
        check(value, schema["not"], path, probe)
        if not probe:
            fields = schema["not"].get("required", [])
            if fields:
                errors.extend(f"{at(path, f)}: not allowed here" for f in fields)
            else:
                errors.append(f"{where}: must not match {show(schema['not'])}")


def load(path, what):
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as e:
        print(f"ERROR: could not read the {what} {path}: {e.strerror or e}. Nothing was checked.")
        sys.exit(2)
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        print(f"ERROR: the {what} {path} is not valid JSON (line {e.lineno}, column {e.colno}: {e.msg}). Nothing was checked.")
        sys.exit(2)


def main(argv):
    args = [a for a in argv if a != "--schema"]
    if "--schema" in argv:
        i = argv.index("--schema")
        if i + 1 >= len(argv):
            print("ERROR: --schema needs a path.")
            return 2
        schema_path = Path(argv[i + 1])
        args = argv[:i] + argv[i + 2:]
    else:
        schema_path = None
    if len(args) != 1:
        print(__doc__.split("\n\n")[1])
        return 2
    target = Path(args[0])
    if schema_path is None:
        kind = re.match(r"[a-z]+", target.name)
        schema_path = SCHEMAS / f"{kind.group(0) if kind else target.stem}.schema.json"
        if not schema_path.exists():
            names = ", ".join(sorted(p.name.split(".")[0] for p in SCHEMAS.glob("*.schema.json")))
            print(f"ERROR: no contract schema for {target.name}. Known contracts: {names}. Use --schema to name one.")
            return 2

    schema = load(schema_path, "schema")
    data = load(target, "file")
    errors = []
    check(data, schema, "", errors)
    rel = schema_path.relative_to(ROOT) if schema_path.resolve().is_relative_to(ROOT) else schema_path
    if not errors:
        print(f"PASS  {target}  ({rel})")
        return 0
    print(f"FAIL  {target}  ({rel})")
    for e in dict.fromkeys(errors):
        print(f"  - {e}")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
