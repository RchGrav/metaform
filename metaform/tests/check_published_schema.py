"""The schema the server publishes to agents must accept every command the full contract accepts."""
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('validator', ROOT / 'validate_metaform.py')
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)
CONTRACT = json.loads((ROOT / 'mcp-tools.proposed.json').read_text())['tools'][0]['inputSchema']
PUBLISHED = json.loads((ROOT / 'mcp-tool.published.json').read_text())['inputSchema']
CASES = json.loads((ROOT / 'conformance' / 'cases.json').read_text())


def calls():
    cases = CASES['cases'] if isinstance(CASES, dict) else CASES
    for case in cases:
        for step in case.get('steps', []):
            if isinstance(step.get('call'), dict):
                yield step['call']


def texts(schema):
    """Every description text in a schema."""
    if isinstance(schema, dict):
        for key, value in schema.items():
            if key == 'description' and isinstance(value, str):
                yield value
            else:
                yield from texts(value)
    elif isinstance(schema, list):
        for value in schema:
            yield from texts(value)


class PublishedSchemaChecks(unittest.TestCase):
    def test_accepts_every_command_the_contract_accepts(self):
        accepted = [call for call in calls() if validator.validate_command(call, CONTRACT) == []]
        self.assertGreater(len(accepted), 200)
        for call in accepted:
            self.assertEqual([], validator.validate_command(call, PUBLISHED), call)

    def test_is_smaller_than_the_contract(self):
        size = lambda schema: len(json.dumps(schema, separators=(',', ':')))
        self.assertLess(size(PUBLISHED), size(CONTRACT) // 2)

    def test_every_description_is_the_contracts_own_text(self):
        contract = ' '.join(texts(CONTRACT))
        for text in texts(PUBLISHED):
            for sentence in filter(None, (part.strip() for part in text.split('. '))):
                self.assertIn(sentence.rstrip('.'), contract, sentence)


if __name__ == '__main__':
    unittest.main()
