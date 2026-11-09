"""Regression checks for concrete schema errors and reference integrity."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('metaform_validator', ROOT / 'validate_metaform.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
SCHEMA = json.loads((ROOT / 'metaform.schema.json').read_text())
BASE = json.loads(Path(str(ROOT) + '/provider-reference-example.json').read_text())


class ContractChecks(unittest.TestCase):
    def ok(self, value):
        self.assertEqual([], module.validate(value, SCHEMA))

    def bad(self, value):
        self.assertTrue(module.validate(value, SCHEMA))

    def relationship(self, **fields):
        doc = deepcopy(BASE)
        doc['code']['application']['wants']['code.sdk'].update(fields)
        return doc

    def test_schema_is_draft_2020_12_valid(self):
        Draft202012Validator.check_schema(SCHEMA)

    def test_owner_native_skills_example_unchanged(self):
        self.ok(json.loads(Path(str(ROOT) + '/owner-skills-example.json').read_text()))

    def test_provider_reference_points_to_tree(self):
        self.ok(BASE)

    def test_provider_can_also_be_receiver(self):
        doc = deepcopy(BASE)
        doc['code']['sdk']['wants'] = {'code.library': {'why': 'Read the data.', 'how': 'Supplies the data.', 'direction': 'inbound'}}
        doc['code']['library'] = {}
        self.ok(doc)

    def test_knowledge_at_referenced_element(self):
        doc = deepcopy(BASE)
        doc['code']['sdk'].update(name='Project SDK', skills=[{'frontmatter': {'name': 'native'}}])
        self.ok(doc)

    def test_all_three_flow_directions(self):
        for direction in ('outbound', 'inbound', 'two-way'):
            with self.subTest(direction=direction):
                self.ok(self.relationship(direction=direction))

    def test_unbuilt_spelling(self):
        self.ok({'code': {'status': 'un_built'}})

    def test_legacy_status_labels_rejected(self):
        for state in ('missing', 'MISSING', 'BKN', 'broken', 'todo', 'TODO'):
            with self.subTest(state=state):
                self.bad({'code': {'status': state}})

    def test_blank_relationship_fields_rejected(self):
        for field in ('why', 'how'):
            for blank in ('', '  ', '\n\t'):
                with self.subTest(field=field, blank=repr(blank)):
                    self.bad(self.relationship(**{field: blank}))

    def test_required_relationship_fields(self):
        for field in ('why', 'how', 'direction'):
            doc = deepcopy(BASE)
            del doc['code']['application']['wants']['code.sdk'][field]
            self.bad(doc)

    def test_provider_properties_cannot_be_copied_under_reference(self):
        for field in ('provider_node', 'properties', 'layers', 'name', 'role', 'technical_name', 'skills', 'wants'):
            with self.subTest(field=field):
                self.bad(self.relationship(**{field: {}}))

    def test_invalid_flow(self):
        self.bad(self.relationship(direction='upstream'))

    def test_wants_as_a_list_is_rejected(self):
        doc = deepcopy(BASE)
        doc['code']['application']['wants'] = [doc['code']['application']['wants']]
        self.bad(doc)

    def test_plain_providers_namespace_branch_allowed(self):
        self.ok({'code': {'wants': {'registry': {}}}})

    def test_scalar_op_and_ef_not_node_metadata(self):
        for field in ('why', 'how'):
            self.bad({'code': {field: 'wrong place'}})
            self.bad({field: 'root cannot bypass node rules'})

    def test_metadata_words_can_be_namespace_branches(self):
        self.ok({'code': {'role': {'registry': {}}, 'name': {'registry': {}}, 'why': {'registry': {}}}})

    def test_plural_object_is_namespace_not_native_array(self):
        self.ok({'code': {'skills': {'registry': {'name': 'Skill registry'}}}})

    def test_native_array_members_are_not_namespace_nodes(self):
        self.ok({'code': {'skills': [{'provider_node': {}, 'wants': 'native', 'technical_name': -20, 'x.y': 1}]}})

    def test_dotted_keys_only_valid_as_provider_references(self):
        self.bad({'code.sdk': {}})
        self.bad({'code': {'system.management': {}}})

    def test_dangling_provider(self):
        doc = deepcopy(BASE)
        del doc['code']['sdk']
        self.bad(doc)

    def test_scalar_and_array_provider_targets_rejected(self):
        for target in ('not an element', []):
            doc = deepcopy(BASE)
            doc['code']['sdk'] = target
            self.bad(doc)

    def test_same_provider_for_different_receivers_allowed(self):
        doc = deepcopy(BASE)
        doc['code']['other'] = deepcopy(doc['code']['application'])
        self.ok(doc)

    def test_invalid_project_relative_addresses(self):
        for address in ('$.code.sdk', 'code..sdk', 'code.sdk.', '', 'code[0].sdk'):
            doc = deepcopy(BASE)
            record = doc['code']['application']['wants'].pop('code.sdk')
            doc['code']['application']['wants'][address] = record
            self.bad(doc)

    def test_technical_name_aligns_with_the_reversed_address(self):
        self.ok({'code': {'engine': {'game': {'technical_name': 'game engine', 'name': 'idtech'}}}})
        for technical in ('engine game', 'game engine code extra', '', 'gaming engine'):
            self.bad({'code': {'engine': {'game': {'technical_name': technical, 'name': 'idtech'}}}})
        self.bad({'code': {'engine': {'game': {'technical_name': 'game engine', 'name': 'game engine'}}}})

    def test_project_metadata_not_required_wrapper(self):
        self.ok({'project': 'Project A', **deepcopy(BASE)})

    def test_json_parser_rejects_duplicate_keys_before_data_loss(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'duplicate.json'
            path.write_text('{"code": {}, "code": {"sdk": {}}}')
            with self.assertRaisesRegex(ValueError, 'Duplicate JSON object key'):
                module.load_json(path)

    def test_registry_uses_current_data_definitions(self):
        registry = json.loads((ROOT / 'mcp-tools.proposed.json').read_text())
        self.assertEqual(['project-map'], [tool['name'] for tool in registry['tools']])
        for tool in registry['tools']:
            for kind in ('inputSchema', 'outputSchema'):
                if kind not in tool:
                    continue
                Draft202012Validator.check_schema(tool[kind])
                for name, definition in SCHEMA['$defs'].items():
                    if '$defs' in tool[kind]:
                        self.assertEqual(definition, tool[kind]['$defs'][name])
        tool_input = registry['tools'][0]['inputSchema']
        for command in ({'code.application': {}}, {'orphaned': {}},
                        {'delete': {'code.sdk': {}}}):
            self.assertFalse(list(Draft202012Validator(tool_input).iter_errors(command)))
        self.assertTrue(list(Draft202012Validator(tool_input).iter_errors(
            {'mode': 'local_functional', 'address': 'code.application'})))

    def test_owner_mashtrac_example_uses_selected_project(self):
        doc = json.loads((ROOT / 'intake-example.json').read_text())
        self.ok(doc['mashtrac'])
        self.assertEqual('cs tracker network protocol', doc['mashtrac']['code']['protocol']['network']['tracker']['cs']['technical_name'])

    def test_uri_is_one_source_link(self):
        self.ok({'code': {'uri': './src/main.c'}})
        self.bad({'code': {'uri': ''}})
        self.bad({'code': {'uri': ['a.c', 'b.c']}})

    def test_old_relationship_fields_are_not_accepted(self):
        doc = deepcopy(BASE)
        doc['code']['application']['wants']['code.sdk'] = {
            'op': 'Use SDK.', 'ef': 'SDK service.', 'ifd': 'receive'
        }
        self.bad(doc)
        doc['code']['application']['wants']['code.sdk'] = {
            'why': 'Use SDK.', 'how': 'SDK service.', 'intent': 'inbound'
        }
        self.bad(doc)
        for old in ('send', 'receive', 'send_receive'):
            with self.subTest(old=old):
                self.bad(self.relationship(direction=old))
        self.bad({'code': {'providers': []}})


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ContractChecks)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    report = {
        'tests_run': result.testsRun,
        'failures': len(result.failures), 'errors': len(result.errors),
        'passed': result.wasSuccessful(),
        'scope': 'Local JSON Schema and reference-validator regression checks only.',
        'not_proven': ['functional naming', 'technical wording', 'intake fidelity', 'database transactions', 'multi-user isolation', 'MCP interoperability', 'running application'],
    }
    (ROOT / 'verification/latest-schema-check-results.json').write_text(json.dumps(report, indent=2) + '\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)
