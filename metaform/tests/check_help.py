"""Each schema that `help` returns must stand alone and take the owner's example of its command."""
import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('validator', ROOT / 'validate_metaform.py')
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)
sys.path.insert(0, str(ROOT / 'python'))
from metaform import reads  # noqa: E402

EXAMPLES = json.loads((ROOT / 'tool-examples.json').read_text())
REQUESTS = EXAMPLES['requests']
# The owner's examples of each command. `map` and a raw dump have no example in the file.
OWN = {
    'add': [REQUESTS[0]],
    'update': [REQUESTS[4]],
    'delete': [REQUESTS[1], REQUESTS[2]],
    'orphaned': [REQUESTS[3]],
    'goto': [EXAMPLES['goto_example']['request']],
    'map': [{'map': {}}],
    'addressed read': [REQUESTS[5]],
    'raw dump': [{'.': {}}],
    'help': [{'help': {}}, {'help': 'add'}],
}


class HelpChecks(unittest.TestCase):
    def test_help_names_every_command(self):
        names = reads.help({})['help']['properties']['help']['enum']
        self.assertEqual(list(OWN), names)

    def test_each_schema_takes_the_example_of_its_command_and_no_other(self):
        for name, examples in OWN.items():
            schema = reads.help(name)['help'][name]
            for example in examples:
                self.assertEqual([], validator.validate_command(example, schema), (name, example))
            for other, others in OWN.items():
                if other != name:
                    for example in others:
                        self.assertTrue(validator.validate_command(example, schema), (name, example))


if __name__ == '__main__':
    unittest.main()
