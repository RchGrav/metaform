"""Check the agreed command input without performing the commands against a service."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('validator', ROOT / 'validate_metaform.py')
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)
REGISTRY = json.loads((ROOT / 'mcp-tools.proposed.json').read_text())
INPUT = next(tool['inputSchema'] for tool in REGISTRY['tools']
             if tool['name'] == 'project-map')
RECEIVER = 'code.protocol.network.tracker.cs'
PROVIDER = 'code.masher.widget'
WANT = {'why': 'Receive the mash data to relay it.',
        'how': 'Prepared mash data packets.', 'intent': 'receive'}


class ToolInputChecks(unittest.TestCase):
    def ok(self, command):
        self.assertEqual([], validator.validate_command(command, INPUT))

    def bad(self, command):
        self.assertTrue(validator.validate_command(command, INPUT))

    def test_add_receiver_want(self):
        self.ok({'add': {RECEIVER: {'wants': {PROVIDER: WANT}}}})

    def test_element_fields_and_native_layers(self):
        self.ok({'add': {PROVIDER: {'name': 'mashbox', 'uri': './src/widgets/mashbox.c',
                                  'skills': [{'frontmatter': {'name': 'native'}, 'x.y': 1}]}}})

    def test_delete_element_empty_object(self):
        self.ok({'delete': {PROVIDER: {}}})
        self.bad({'delete': {PROVIDER: None}})

    def test_delete_relation_uses_addresses(self):
        self.ok({'delete': {RECEIVER: {'wants': [PROVIDER]}}})
        self.bad({'delete': {RECEIVER: {'wants': [{PROVIDER: None}]}}})
        self.bad({'delete': {RECEIVER: {'wants': [{PROVIDER: WANT}]}}})
        self.bad({'delete': {RECEIVER: {'wants': []}}})
        self.bad({'delete': {RECEIVER: {'wants': [PROVIDER, PROVIDER]}}})

    def test_orphan_query_and_addressed_read(self):
        self.ok({'orphaned': {}})
        self.ok({PROVIDER: {}})
        self.bad({'orphaned': {'scope': 'all'}})
        self.bad({PROVIDER: {'role': 'SE'}})

    def test_goto(self):
        self.ok({'goto': PROVIDER})
        self.ok({'goto': '.'})
        self.ok(json.loads((ROOT / 'tool-examples.json').read_text())['goto_example']['request'])
        self.bad({'goto': {}})
        self.bad({'goto': 'not an address'})
        self.bad({'goto': PROVIDER, 'orphaned': {}})

    def test_update_null_removes_property(self):
        self.ok({'update': {PROVIDER: {'role': None}}})
        self.ok({'update': {PROVIDER: {'uri': None}}})
        self.bad({'delete': {PROVIDER: {'role': None}}})

    def test_partial_want_update(self):
        self.ok({'update': {RECEIVER: {'wants': {PROVIDER: {'intent': 'send_receive'}}}}})
        self.bad({'update': {RECEIVER: {'wants': {PROVIDER: {}}}}})
        self.bad({'update': {RECEIVER: {'wants': {PROVIDER: {'why': None}}}}})

    def test_invalid_add_wants(self):
        for field in WANT:
            fields = deepcopy(WANT)
            del fields[field]
            self.bad({'add': {RECEIVER: {'wants': {PROVIDER: fields}}}})
        self.bad({'add': {RECEIVER: {'wants': [{PROVIDER: WANT}]}}})
        self.bad({'add': {RECEIVER: {'wants': [PROVIDER]}}})
        self.bad({'add': {RECEIVER: {'wants': {PROVIDER: dict(WANT, intent='request')}}}})

    def test_one_operation_one_receiver(self):
        self.bad({})
        self.bad({'add': {}})
        self.bad({'add': {RECEIVER: {}}, 'delete': {PROVIDER: {}}})
        self.bad({'add': {RECEIVER: {'name': 'mashtrac'}, PROVIDER: {'name': 'mashbox'}}})
        self.bad({'changes': {'code': {}}, 'expected_revision': 'r1', 'operation_id': 'old'})

    def test_addresses_and_technical_name(self):
        for address in ('$.mashtrac.code.masher.widget', 'code..widget', 'code[0].widget', ''):
            self.bad({address: {}})
            self.bad({'delete': {address: {}}})
        self.ok({'update': {RECEIVER: {'technical_name': 'cs tracker network protocol'}}})
        self.bad({'update': {PROVIDER: {'technical_name': 'cs tracker network protocol'}}})

    def test_ref_properties_stay_on_actual_element(self):
        self.bad({'add': {RECEIVER: {'wants': {PROVIDER: dict(WANT, uri='./wrong.c')}}}})

    def test_error_remediation_is_valid_input(self):
        example = json.loads((ROOT / 'tool-examples.json').read_text())
        for command in example['requests']:
            self.ok(command)
        self.ok(example['referenced_delete_error']['remediation'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
