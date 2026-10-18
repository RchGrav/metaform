"""The tool catalog, MCP-003: Metaform's tools found by purpose, and the tools each agent's role is given.

An agent knows what it is trying to do before it knows which tool does it, and every tool it is listed it reads and
carries, so the server lists by purpose. Each tool belongs to a category, the purpose it serves: its verb's own
`category`, else the one given it here, else its module's. A connection whose listing follows its session is listed
one tool, metaform_catalog, and the tools of the one category it has open: called with nothing, it says each category's
purpose; with a category, it opens it, so its tools are listed in place of the last one's; with search, it finds tools
from words for what the agent wants to do, in any category; with tool and arguments, it runs one, for an AI tool that
keeps the list it was first given. A connection whose listing names no session, such as an HTTP client on the July
2026 wire, which has no session header, is listed every tool its role is given, since no category it opens could
change what it is listed.

Every execution role may discover each category unless the person's configured roles_without_authority holds it
back from steering. Authored responsibility does not grant or remove tool authority. A role starts with the category
its first task needs open, so the
tool its first message names is listed at once: a worker's ticket category, an intake's intake category; a role whose
first task needs one tool alone, a talk or a sentinel reading its node, starts with that tool and no category open.
"""
from __future__ import annotations

import os
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from metaform import prompt_files, settings
from metaform.module import CATEGORY_NAMES, Module, Verb

CATALOG = 'metaform_catalog'  # the one tool every connection is listed in catalog mode
OPEN_KEY = 'catalog:open'  # the ledger key of the category a session has open; shown.KEPT_THROUGH_COMPACTION keeps it

# The tools each category holds, in the order an agent reads them, where the verb does not name its own: the tool's home
# category first. A tool may serve two purposes, such as intake_start, which also opens a verification pass that adds
# a part to the map, so it is found from either.
CATEGORY_TOOLS: dict[str, tuple[str, ...]] = {
    'orient': ('map_where', 'map_find', 'map_search', 'map_roots', 'map_element', 'map_node', 'map_children',
               'map_joins', 'map_identity', 'map_context', 'map_links', 'map_citing', 'map_item', 'map_history',
               'map_layers', 'map_layer', 'map_bases', 'map_glossary', 'map_cypher',
               'map_challenges'),
    'ticket': ('map_work', 'map_where', 'dispatch_handoff', 'dispatch_link', 'map_messages', 'map_reply',
               'map_answer', 'dispatch_attach', 'dispatch_timer'),
    'remember': ('memory_read_graph', 'memory_search_nodes', 'memory_open_nodes', 'memory_create_entities',
                 'memory_add_observations', 'memory_create_relations', 'memory_joins', 'memory_note', 'memory_graph',
                 'memory_orphaned', 'memory_rekey', 'memory_unjoin', 'memory_delete_entities',
                 'memory_delete_observations', 'memory_delete_relations'),
    'coordinate': ('dispatch_peers', 'dispatch_note', 'dispatch_notes', 'agents_resolve', 'agents_roles',
                   'agents_receipts', 'mcp_a2a_peers', 'mcp_a2a_send',
                   'mcp_a2a_exchanges', 'mcp_a2a_cancel'),
    'change-map': ('map_refine', 'map_knowledge', 'map_term', 'map_promote', 'intake_start', 'map_tag', 'map_untag',
                   'map_select', 'map_mask', 'map_clear', 'map_hide', 'map_unhide', 'map_reexamined', 'map_critic'),
    'intake': ('intake_prompt', 'intake_schema', 'intake_start', 'intake_element', 'intake_purpose', 'intake_show',
               'intake_remove', 'intake_finish', 'intake_status'),
    'steer': ('dispatch_start', 'dispatch_agents', 'dispatch_sessions', 'dispatch_message', 'dispatch_wait',
              'dispatch_stop', 'dispatch_talk', 'dispatch_system', 'dispatch_intake', 'dispatch_signals',
              'dispatch_resume', 'dispatch_interrupt', 'dispatch_cancel', 'dispatch_broadcast',
              'dispatch_broadcasts', 'dispatch_autostart', 'dispatch_stop-all', 'dispatch_propose', 'dispatch_claim',
              'dispatch_claims', 'dispatch_merges', 'dispatch_review', 'dispatch_prep', 'dispatch_fork',
              'dispatch_options', 'dispatch_tune', 'dispatch_spend', 'dispatch_registry', 'dispatch_recover',
              'dispatch_reset', 'dispatch_permit', 'dispatch_publication', 'agents_roles', 'agents_role',
              'agents_sent', 'agents_override', 'agents_drop'),
    'show': ('web_start', 'web_restart', 'web_stop'),
    'workflow': ('metaform_skills',),
    'setup': ('metaform_set', 'metaform_register', 'metaform_instructions', 'metaform_prompts', 'metaform_prompt',
              'metaform_save_prompt', 'metaform_add_origin', 'metaform_list_origins', 'metaform_add_variant',
              'metaform_list_variants', 'metaform_extract', 'metaform_clear_project', 'map_bases', 'map_add-base',
              'map_activate', 'map_remove-base', 'map_collapse', 'fork_init', 'fork_upkeep'),
    'report': ('metaform_feedback', 'metaform_list_reports', 'metaform_read_report', 'metaform_instructions'),
}
# The category of a module's tools that no category above names and whose verb names none.
MODULE_CATEGORY: dict[str, str] = {
    'map': 'orient', 'memory': 'remember', 'dispatch': 'steer', 'intake': 'intake', 'web': 'show',
    'workflow': 'workflow', 'mcp': 'coordinate', 'agents': 'steer', 'orchestration': 'coordinate',
    'fork': 'setup', 'twilio': 'setup',
    'paperclip': 'coordinate', 'metaform': 'setup'}
FALLBACK = 'setup'  # a module this table does not know, whose verbs name no category

# The category open when an execution role starts, containing the first message's named tool.
ROLE_OPENS: dict[str, str] = {'worker': 'ticket', 'prep': 'ticket', 'intake': 'intake'}
# The tools listed beside the catalog to a role that starts with no category open, the one its first message names:
# a talk and a sentinel read the node they were given before anything else, and the 20 other orient tools would come
# with a category opened for it.
ROLE_FIRST: dict[str, tuple[str, ...]] = {'talk': ('map_where',), 'sentinel': ('map_where',)}
# What a role the person holds back, roles_without_authority, never writes over a tool: the ops of a tool it is refused,
# and the arguments only those ops and the board read, left out of the tool's schema and its guide for that role, so
# its agent is not handed the board's controls. A tool not named keeps its schema whole.
HELD_OPS: dict[str, tuple[str, ...]] = {'map_work': ('add', 'move', 'distribute', 'glyphs')}
HELD_ARGUMENTS: dict[str, tuple[str, ...]] = {
    'map_work': ('column', 'position', 'held', 'reviewed', 'agent', 'hold', 'glyph', 'eligible', 'after_work', 'agents',
                 'links', 'by', 'title', 'task'),
    'dispatch_handoff': ('full',)}  # the full brief, no longer sent to agents, is the person's to read
STEER = 'steer'  # what a role the person holds back, roles_without_authority, never opens
ALWAYS = ('metaform_feedback',)  # runs for every role, so a fault can always be reported, MCP-006

assert set(CATEGORY_TOOLS) == set(CATEGORY_NAMES), 'one entry for each category the chassis names'


def role() -> str | None:
    """The role of the agent this server serves, from METAFORM_ROLE, which dispatch's runner sets on its agent's MCP
    server; None for the person's own sessions."""
    named = os.environ.get('METAFORM_ROLE') or ''
    return named if named and named != 'none' else None


def held(folder: Path, named: str | None) -> bool:
    """Whether the person holds the role back from steering agents and writing tickets, roles_without_authority."""
    if named is None:
        return False
    try:
        return named in (settings.value('roles_without_authority', folder) or ())
    except LookupError:
        return False


def allowed(folder: Path, named: str | None = None) -> tuple[str, ...]:
    """All categories, in chassis order, except steering when the person's configuration holds the role back."""
    named = role() if named is None else named
    found = set(CATEGORY_NAMES)
    if held(folder, named):
        found.discard(STEER)
    return tuple(one for one in CATEGORY_NAMES if one in found)


def opens(named: str | None = None) -> str | None:
    """The category open when the role's session starts, None for a role that starts with the categories alone."""
    return ROLE_OPENS.get((role() if named is None else named) or '')


def first(named: str | None = None) -> tuple[str, ...]:
    """The tools listed beside the catalog while no category is open, the ones the role's first message names."""
    return ROLE_FIRST.get((role() if named is None else named) or '', ())


# The roles that act for the person, beside the person's own sessions: they are given what a verb says only to the
# person, Verb.person_details, such as how the person writes a ticket.
FOR_PERSON = ('system', 'sentinel')


def for_person(named: str | None = None) -> bool:
    """Whether the agent this server serves acts for the person: the person's own sessions and FOR_PERSON."""
    named = role() if named is None else named
    return named is None or named in FOR_PERSON


def held_back(folder: Path, name: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """The ops and the arguments of a tool left out for the role this server serves, HELD_OPS and HELD_ARGUMENTS: both
    empty unless the person holds the role back."""
    if not held(folder, role()):
        return (), ()
    return HELD_OPS.get(name, ()), HELD_ARGUMENTS.get(name, ())


def categories_of(name: str, verb: Verb | None, module: Module | None) -> tuple[str, ...]:
    """The categories a tool is found under, its home first: its verb's own, else each category naming it, else its
    module's."""
    if verb is not None and verb.category is not None:
        return (verb.category,)
    named = tuple(category for category, members in CATEGORY_TOOLS.items() if name in members)
    if named:
        home = next((category for category in named if CATEGORY_TOOLS[category][0] == name), None)
        return (home, *(one for one in named if one != home)) if home else named
    owner = module.id if module is not None else name.split('_', 1)[0]
    return (MODULE_CATEGORY.get(owner, FALLBACK),)


def grouped(names: Iterable[str], declared: dict[str, tuple[Module, Verb]]) -> dict[str, list[str]]:
    """Each category, in CATEGORY_NAMES order, with the tools of `names` it holds, in its declared order, then by
    name for those it holds by module."""
    found: dict[str, list[str]] = {category: [] for category in CATEGORY_NAMES}
    for name in names:
        module, verb = declared.get(name, (None, None))
        for category in categories_of(name, verb, module):
            found[category].append(name)
    order = {category: {tool: index for index, tool in enumerate(members)}
             for category, members in CATEGORY_TOOLS.items()}
    return {category: sorted(tools, key=lambda tool: (order[category].get(tool, len(order[category])), tool))
            for category, tools in found.items()}


def in_scope(name: str, declared: dict[str, tuple[Module, Verb]], folder: Path, named: str | None = None) -> bool:
    """Whether a tool is given to the role: one of its categories is one the role may open."""
    if name in ALWAYS or name == CATALOG:
        return True
    module, verb = declared.get(name, (None, None))
    return bool(set(categories_of(name, verb, module)) & set(allowed(folder, named)))


def purpose(category: str) -> str:
    """What a category is for, from the mcp module's prompts.xml, `category_<name>`; its name when the line is empty."""
    return prompt_files.module('mcp', 'category_' + category.replace('-', '_')) or category


def signature(schema: dict[str, Any]) -> str:
    """A tool's arguments as an agent plans a call from them: each name, required ones bare and the rest with `?`."""
    properties: dict[str, Any] = schema.get('properties') or {}
    required: set[str] = {str(one) for one in schema.get('required') or ()}
    return ', '.join(name if name in required else f'{name}?' for name in properties)


WORD = re.compile(r'[a-z0-9]+')


def words(text: str) -> set[str]:
    return set(WORD.findall(text.lower()))


def ranked(query: str, described: dict[str, str], homes: dict[str, str]) -> list[str]:
    """The tools whose name, description and category's purpose hold the most of the query's words, each as a prefix
    of a word there, best first; a tool that holds none is left out."""
    asked = words(query)
    if not asked:
        return []
    scored: list[tuple[int, str]] = []
    for name, said in described.items():
        held = words(f'{name.replace("_", " ")} {said} {homes.get(name, "")} {purpose(homes.get(name, ""))}')
        hits = sum(1 for word in asked if any(one.startswith(word) for one in held))
        named = sum(1 for word in asked if word in name)
        if hits:
            scored.append((-(hits * 2 + named), name))
    return [name for _, name in sorted(scored)]
