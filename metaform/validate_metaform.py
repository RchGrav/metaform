"""Validate Metaform JSON shape and cross-reference integrity.

Usage: python3 metaform/validate_metaform.py document.json [schema.json]
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
        errors.extend(technical_name_errors('.'.join(['$'] + path), path, node))
        for key, value in node.items():
            if key == 'wants' and is_want_map(value):
                for address in value:
                    target = document
                    for part in address.split('.'):
                        if not isinstance(target, dict) or part not in target:
                            target = None
                            break
                        target = target[part]
                    if not isinstance(target, dict):
                        errors.append(
                            f"{'.'.join(['$'] + path)}.wants: "
                            f"{address} does not resolve to a namespace element"
                        )
            elif isinstance(value, dict):
                walk(value, path + [key])
            # Other arrays are native layers: never traverse their members
            # as namespace nodes, even when a native member has wants/name.

    walk(document, [])
    return errors


def reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'Duplicate JSON object key: {key}')
        result[key] = value
    return result


def validate_command(command, input_schema):
    """Check command shape and address-local constraints; do not apply writes.

    Reference resolution, permissions and deletion preconditions require the
    authoritative project state and belong to the eventual service.
    """
    Draft202012Validator.check_schema(input_schema)
    errors = [
        f"{error.json_path}: {error.message}"
        for error in Draft202012Validator(input_schema).iter_errors(command)
    ]
    if errors:
        return errors
    operation = next(iter(command))
    if operation not in ('add', 'update'):
        return errors
    address, fields = next(iter(command[operation].items()))
    errors.extend(technical_name_errors(address, address.split('.'), fields))
    return errors


def technical_name_errors(label, segments, fields):
    """TECHNICAL_NAME_ALIGNMENT_FAILURE and CANONICAL_NAME_COLLISION_FAILURE (documentation set, 6.1, 6.2):
    the technical name is the same number of leading words of the reversed, space-separated address,
    and `name`, the project's own name for the element, must differ from it."""
    technical = fields.get('technical_name')
    if not isinstance(technical, str):
        return []
    reversed_words = ' '.join(segment.replace('_', ' ') for segment in reversed(segments)).split()
    words = technical.split()
    errors = []
    if not words or words != reversed_words[:len(words)]:
        errors.append(f'{label}.technical_name: "{technical}" does not match the leading words of '
                      f'the reversed address "{" ".join(reversed_words)}"')
    if fields.get('name') == technical:
        errors.append(f'{label}.name: must not match technical_name "{technical}"')
    return errors


def is_want_map(value):
    """A wants dictionary keyed by provider address, as opposed to a namespace branch named wants."""
    return (isinstance(value, dict) and bool(value)
            and all(isinstance(record, dict) and ({'why', 'how', 'intent'} & set(record))
                    for record in value.values()))


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
    print('PASS: JSON shape, provider references and technical name alignment.')
    print('Functional naming, plurality and the meaning of why/how require review.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
