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


def standing_overlays() -> dict[str, dict[str, object]]:
    """The overlays every project is given beside its wants, each by its address beneath the project's name with
    its definition as `add` takes it. They are ordinary overlays: read, written and shown as any other. Their fields
    are the ones tickets and memories already had: a ticket's id, task, note, kind, held, taken_by, done, outcome and
    its count of steps and steps done,
    and a memory as the reference memory server keeps it, an entity of a type holding observations of one fact each,
    and the specification's blocks (`specification`)."""
    from metaform.project import specification
    return {
        'overlay.tickets': {
            'description': 'Work assigned at this element: each record is one ticket, from asked to done.',
            'instruction': ('Add one record for each piece of work. Change one by its position with update: taken_by '
                            'when an agent takes it, note to say where it stands, done and outcome when it ends. On '
                            'the board a ticket is done once done is set, doing once taken, in the backlog while '
                            'held, and to do otherwise.'),
            'id': {'type': 'text', 'rule': "A short id that stays the same for the ticket's life.",
                   'example': 't-3f9a'},
            'title': {'type': 'text', 'rule': 'One line that names the work.', 'example': 'Ring when a timer ends'},
            'task': {'type': 'text', 'rule': 'What to do, in full, for an agent that knows nothing else of it.',
                     'example': 'Make watch ring each timer as it ends, also one started while watch runs.'},
            'kind': {'type': 'broken | flawed | enhancement', 'rule': 'What kind of work it is; left out for a plain task.',
                     'example': 'broken', 'optional': True},
            'held': {'type': 'boolean', 'rule': 'True while it waits in the backlog and is not to be started.',
                     'example': False, 'optional': True},
            'taken_by': {'type': 'text', 'rule': 'Who took it, once someone has.', 'example': 'claude',
                         'optional': True},
            'note': {'type': 'text', 'rule': 'Where it stands now, by whoever last worked on it.',
                     'example': 'watch now reads the timers again before each sleep.', 'optional': True},
            'done': {'type': 'text', 'rule': 'When it ended, as a date and time; left out while it is open.',
                     'example': '2026-11-16T09:30:00Z', 'optional': True},
            'outcome': {'type': 'completed | cancelled | failed', 'rule': 'How it ended.', 'example': 'completed',
                        'optional': True},
            # a worksheet's progress on the ticket, as the old store's work record kept it (kickoff 2026-11-17,
            # t-legacy-keep): added optional, so a project given tickets before keeps every record valid (F03)
            'steps': {'type': 'number', 'rule': 'How many steps the work has, once they are counted.', 'example': 2,
                      'optional': True},
            'steps_done': {'type': 'number', 'rule': 'How many of its steps are done.', 'example': 1,
                           'optional': True},
        },
        'overlay.memories': {
            'description': ('What is worth keeping about this element: each record is one observation of a named '
                            'entity.'),
            'instruction': ('Add one record for each fact, one fact in one sentence. Records that share an entity '
                            'are that entity\'s observations.'),
            'entity': {'type': 'text', 'rule': 'The name of what the fact is about.', 'example': 'watch command'},
            'entity_type': {'type': 'text', 'rule': 'What kind of thing the entity is.', 'example': 'behaviour'},
            'observation': {'type': 'text', 'rule': 'One fact, in one sentence.',
                            'example': 'watch loads the timers when it starts, so one started later is not rung by it.'},
        },
        # the specification's prose at the elements it describes (kickoff 2026-11-17 Phase 4, F06)
        specification.DEFINITION_PATH: specification.DEFINITION,
    }


COMMANDS = ('add', 'update', 'delete', 'orphaned', 'map', 'help')
HELP_NAMES = ('add', 'update', 'delete', 'orphaned', 'map', 'addressed read', 'overlay', 'help', 'intake')

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
            'status': 'unbuilt for functionality that is intended and not built yet.',
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
                 "wants record names its element and gives only the fields to change. A list written to another overlay "
                 "replaces that overlay's list at the element; a record that gives its position, its place in the "
                 "list counted from 0, changes that one record and leaves the others as they are. A read gives each "
                 "record its record id and revision: give them with the position, and an edit made from a read that "
                 "is no longer current is refused, RECORD_MOVED, RECORD_GONE or RECORD_CHANGED, instead of changing "
                 "another record."),
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
                 "another element wants is not deleted; the refusal returns the command that removes that want. "
                 "Records of another overlay are removed by their positions, {\"<overlay>\": [0, 2]}, and the "
                 "records after them close up."),
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
        'does': ("With a project's name, returns the base map: the address of every element (a bare branch on the "
                 "way to one is left out), each want as a pair (the element that holds it, then the wanted "
                 "element), the Defining Elements, and the names of the overlays defined. It returns no fields. An "
                 "overlay's definition is read at its address beneath overlay. With {}, returns the names of the "
                 "projects."),
        'examples': [{'map': 'mashtrac'}, {'map': {}}],
    },
    'addressed read': {
        'does': ("A key that is a path reads that element: its own fields, its wants, the elements whose wants name "
                 "it (wanted_by), and the names of the other overlays that hold records there (overlays). To add an "
                 "overlay's records to the answer, name it with {} as its value. A path beneath overlay reads that "
                 "overlay's definition, in the form it is written in. A project's name alone reads the project's own "
                 "fields, id, name and project, which add and update write at that same one-word path."),
        'examples': [{'mashtrac.code.masher.widget': {}},
                     {'mashtrac.code.masher.widget': {'project_specifications': {}}}],
    },
    'overlay': {
        'does': ("An overlay is a list of records an element can hold, such as its wants. It exists once it is "
                 "defined: add its definition at a path beneath <project>.overlay. The definition holds a "
                 "description and an instruction, and one entry for each field of a record. A field's entry holds "
                 "its type, the rule its value follows and an example, and optional: true when a record may leave it "
                 "out. The overlay's key is the steps after overlay, read in reverse and joined with underscores: "
                 "overlay.specifications.project is written on an element as project_specifications. Records are "
                 "then written under that key with add, as a list. Reading the definition's path returns it with "
                 "its key."),
        'fields': {
            'description': 'What the overlay holds.',
            'instruction': 'How an agent writes a record of it.',
            '<field>': ('One entry for each field of a record: {"type": ..., "rule": ..., "example": ...}. type is '
                        'text, number, boolean or address, or the allowed values written "first | second | third".'),
        },
        'examples': [
            {'add': {'mashtrac.overlay.concerns': {
                'description': 'What an examination found wrong at an element.',
                'instruction': 'One record for each finding, with where it shows.',
                'mark': {'type': 'missing | broken | exclude', 'rule': 'What kind of finding it is.',
                         'example': 'broken'},
                'finding': {'type': 'text', 'rule': 'One sentence that states it.',
                            'example': 'The relay drops packets that arrive while it reconnects.'},
                'evidence': {'type': 'text', 'rule': 'The uri that shows it.', 'example': './src/relay.c#L88',
                             'optional': True}}}},
            {'add': {'mashtrac.code.masher.widget': {'concerns': [
                {'mark': 'broken', 'finding': 'The relay drops packets that arrive while it reconnects.'}]}}},
            {'mashtrac.overlay.concerns': {}},
        ],
    },
    'help': {
        'does': '{} lists the names help takes. A command name returns what the command does, its fields and examples.',
        'examples': [{'help': {}}, {'help': 'add'}],
    },
}
