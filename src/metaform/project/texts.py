"""The fixed text of the project tool: what `help` answers, and the definition of the wants overlay.

Ported from the earlier build's `metaform/tool-help.json` (archive of 2026-11-15). Every example and every sentence of
the want definition is the founder's; the help text is changed only where this tool differs from that build: paths
lead with the project's name, an element holds one `ref`, there is no `goto` or raw dump, `map` and `orphaned` take a
project's name, and other knowledge sits in overlays keyed by their definition. The intake procedure is served
separately and has no entry here.
"""
from __future__ import annotations

ROLES = ('Artifact Type', 'Defining Element', 'Supporting Element', 'Coupled Element', 'Notable Element',
         'Vested Beneficiary', 'Upstream Dependency', 'Downstream Dependant')
# The intake procedure's abbreviations, each answered with the role's full name.
ROLE_WORDS = {'AT': 'Artifact Type', 'DE': 'Defining Element', 'SE': 'Supporting Element', 'CE': 'Coupled Element',
              'NE': 'Notable Element', 'CQU': 'Vested Beneficiary', 'UD': 'Upstream Dependency',
              'DD': 'Downstream Dependant', 'Cestui Que Use': 'Vested Beneficiary'}
ROLE_PLACEHOLDER = '<' + ', '.join(ROLES[:-1]) + ' or ' + ROLES[-1] + '>'

# The founder's want sentence, tool-help.json add.want_sentence, word for word.
WANT_SENTENCE = '{this.address} ({this.name}) requires {other.address} ({other.name}) in order to {why}, which {how}.'
WANT_WHY = ("Bare infinitive verb phrase. State the active goal as a sentence fragment beginning with a base action "
            "verb. Do not include a leading 'to', subject nouns, or any words ending in -ing.")
WANT_HOW = ("Third-person singular present indicative verb phrase. State how the provider satisfies the goal beginning "
            "with a present-tense verb ending in -s or -es that agrees with 'which'. Do not include subject nouns, "
            "'by', or any words ending in -ing.")
WANTS_DESCRIPTION = ("A list of want records. A record holds element (the wanted element's address), why, how, "
                     "direction (send, receive or both) and ref (the uri of the one artifact the want is about). An "
                     "element may hold several wants on the same element, one for each artifact or purpose. The wanted "
                     "element is created at its own address if it is not there.")
WANTS_INSTRUCTION = 'why and how are sentence fragments that complete the sentence below.\n' + WANT_SENTENCE


def wants_definition(project: str) -> dict[str, dict[str, str | bool]]:
    """The parts of `<project>.overlay.wants` that the store writes into a new project, by address without the
    project's name. The rules are the founder's field lines of tool-help.json, the examples the founder's values
    from its want sentence and tool-examples.json, with the wanted element's path led by the project's name."""
    return {
        'overlay': {},
        'overlay.wants': {'description': WANTS_DESCRIPTION, 'instruction': WANTS_INSTRUCTION},
        'overlay.wants.element': {'type': 'address', 'rule': "The wanted element's address.",
                                  'example': f'{project}.code.masher.widget'},
        'overlay.wants.why': {'type': 'text', 'rule': WANT_WHY,
                              'example': 'drain raw frames from the network interface card'},
        'overlay.wants.how': {'type': 'text', 'rule': WANT_HOW,
                              'example': 'holds descriptor pointers across contiguous memory segments'},
        'overlay.wants.direction': {'type': 'send | receive | both', 'rule': 'send, receive or both',
                                    'example': 'receive'},
        'overlay.wants.ref': {'type': 'text', 'rule': 'The uri of the one artifact the want is about.',
                              'example': './src/widgets/mashbox.c', 'optional': True},
    }


HELP_NAMES = ('add', 'update', 'delete', 'orphaned', 'map', 'addressed read', 'help')

_WIDGET = {'technical_name': 'widget masher', 'name': 'mashbox', 'role': 'Coupled Element',
           'ref': './src/widgets/mashbox.c'}
_WANT = {'element': 'mashtrac.code.masher.widget', 'why': 'Receive the mash data to relay it.',
         'how': 'Prepared mash data packets.', 'direction': 'receive'}

HELP: dict[str, object] = {
    'add': {
        'does': ("Adds an element, or adds fields and overlay records to an element that exists. The key is the "
                 "element's path, which starts with the project's name. A list grows; any other field is written. "
                 "One command names one element."),
        'fields': {
            'technical_name': ("The short practitioner name: the leading words of the address after the project's "
                               "name, read in reverse."),
            'name': 'The name this project gives the element.',
            'role': ("Artifact Type, Defining Element, Supporting Element, Coupled Element, Notable Element, Vested "
                     "Beneficiary, Upstream Dependency or Downstream Dependant. The intake procedure defines them."),
            'ref': ("The entry point of this functionality in the material, or a discrete reference that shows it, as "
                    "one text: a path from the project folder, a URL, or project://<name> for another project's map. "
                    "It is not a list of every file; more pointers belong in an overlay."),
            'status': 'un_built for functionality that is intended and not built.',
            'wants': ("A list of want records. A record holds element (the wanted element's path), why, how, "
                      "direction (send, receive or both) and ref (the uri of the one artifact the want is about). An "
                      "element may hold several wants on the same element, one for each artifact or purpose. The "
                      "wanted element is created at its own address if it is not there. why and how are sentence "
                      "fragments that complete the sentence below."),
            '<overlay>': ("A list of records of an overlay defined beneath <project>.overlay. Read the definition for "
                          "its fields: {\"<project>.overlay.<steps>\": {}}."),
        },
        'examples': [{'add': {'mashtrac.code.masher.widget': _WIDGET}},
                     {'add': {'mashtrac.code.protocol.network.tracker.cs': {'wants': [_WANT]}}}],
        'want_sentence': {
            'sentence': WANT_SENTENCE,
            'why': WANT_WHY + ' Example: drain raw frames from the network interface card',
            'how': WANT_HOW + ' Example: holds descriptor pointers across contiguous memory segments',
        },
    },
    'update': {
        'does': ("Changes fields of an element. A field set to null is removed; a field left out is unchanged. A "
                 "wants record names its element and gives only the fields to change."),
        'fields': {
            'technical_name, name, role, ref, status': 'As in add.',
            'wants': ("A list of records. Each holds element, and ref to say which want when the element has "
                      "several, and the fields to change. {\"help\": \"add\"} gives the sentence that why and how "
                      "complete."),
            '<overlay>': 'A list replaces the list that is there; null removes it.',
        },
        'examples': [{'update': {'mashtrac.code.masher.widget': {'role': None}}}],
    },
    'delete': {
        'does': ("Deletes an element with {}, or removes wants by naming their elements. A want named by its element "
                 "and ref, {\"element\": \"<path>\", \"ref\": \"<ref>\"}, removes that one want. An element that "
                 "another element wants is not deleted; the refusal returns the command that removes that want."),
        'examples': [{'delete': {'mashtrac.code.protocol.network.tracker.cs': {
                         'wants': ['mashtrac.code.masher.widget']}}},
                     {'delete': {'mashtrac.code.masher.widget': {}}}],
    },
    'orphaned': {
        'does': ("Returns the elements of a project that no element wants, each with its own fields. Being orphaned "
                 "does not mean an element should be deleted."),
        'examples': [{'orphaned': 'mashtrac'}],
    },
    'map': {
        'does': ("With a project's name, returns every address, each want as a pair (the element that holds it, then "
                 "the wanted element), and the Defining Elements. It returns no fields. The overlays are the "
                 "addresses beneath overlay. With {}, returns the names of the projects."),
        'examples': [{'map': 'mashtrac'}, {'map': {}}],
    },
    'addressed read': {
        'does': ("A key that is a path reads that element's own fields, the elements whose wants name it "
                 "(wanted_by), and the number of records of each overlay that holds records there (overlays). To add "
                 "an overlay's records to the answer, name it with {} as its value. A path beneath overlay reads "
                 "that overlay's definition."),
        'examples': [{'mashtrac.code.masher.widget': {}}, {'mashtrac.code.masher.widget': {'wants': {}}}],
    },
    'help': {
        'does': '{} lists the names help takes. A command name returns what the command does, its fields and examples.',
        'examples': [{'help': {}}, {'help': 'add'}],
    },
}
