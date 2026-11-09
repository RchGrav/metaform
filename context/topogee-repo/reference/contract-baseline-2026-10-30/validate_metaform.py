"""Validate Metaform JSON shape and cross-reference integrity.

Usage: python /workspace/validate_metaform.py document.json [schema.json]
Requires jsonschema. Does not rewrite input or certify functional language.
"""
from pathlib import Path
import json
import sys

from jsonschema import Draft202012Validator


def validate(document, schema):
    Draft202012Validator.check_schema(schema)
    errors = [
        f"{error.json_path}: {error.message}"
        for error in Draft202012Validator(schema).iter_errors(document)
    ]
    if errors:
        return errors

    def walk(node, path):
        if not isinstance(node, dict):
            return
        count = node.get('name_length')
        if isinstance(count, int) and not isinstance(count, bool) and count > len(path):
            errors.append(
                f"{'.'.join(['$'] + path)}.name_length: {count} exceeds "
                f"the {len(path)} namespace segments at this element"
            )
        for key, value in node.items():
            if key == 'providers' and isinstance(value, list):
                seen = set()
                for member in value:
                    for address in member:
                        if address in seen:
                            errors.append(
                                f"{'.'.join(['$'] + path)}.providers: "
                                f"duplicate provider reference {address}"
                            )
                        seen.add(address)
                        target = document
                        for part in address.split('.'):
                            if not isinstance(target, dict) or part not in target:
                                target = None
                                break
                            target = target[part]
                        if not isinstance(target, dict):
                            errors.append(
                                f"{'.'.join(['$'] + path)}.providers: "
                                f"{address} does not resolve to a namespace element"
                            )
            elif isinstance(value, dict):
                walk(value, path + [key])
            # Other arrays are native layers: never traverse their members
            # as namespace nodes, even when a native member has providers/name.

    walk(document, [])
    return errors


def reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'Duplicate JSON object key: {key}')
        result[key] = value
    return result


def load_json(path):
    return json.loads(Path(path).read_text(), object_pairs_hook=reject_duplicate_keys)


def main():
    if len(sys.argv) not in (2, 3):
        print(__doc__.strip())
        return 2
    try:
        document = load_json(sys.argv[1])
        schema_path = Path(sys.argv[2]) if len(sys.argv) == 3 else Path(__file__).with_name('metaform.schema.json')
        errors = validate(document, load_json(schema_path))
    except (OSError, ValueError) as error:
        print(f'FAIL: {error}')
        return 1
    if errors:
        print('FAIL:\n' + '\n'.join(errors))
        return 1
    print('PASS: JSON shape, provider references, uniqueness and name_length bounds.')
    print('Functional naming, plurality and ASD-STE100 language require semantic review.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
