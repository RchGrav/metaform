"""Refactor's optional JavaScript function inventory, including anonymous callbacks."""
from __future__ import annotations

import importlib
from typing import Any

SUFFIXES = ('.js', '.jsx', '.mjs', '.cjs')
FUNCTIONS = {'function_declaration', 'function_expression', 'arrow_function', 'method_definition',
             'generator_function', 'generator_function_declaration'}


def parse(path: str, source: bytes) -> dict[str, Any]:
    """Extract source-local identities without assuming they match a graph index's identities.

    Imports happen when parsing is requested, so declaring the capability does not load its optional
    native libraries. The caller can fall back to indexed declarations if a dependency is unavailable.
    """
    ts = importlib.import_module('tree_sitter')
    grammar = importlib.import_module('tree_sitter_javascript')
    tree = ts.Parser(ts.Language(grammar.language())).parse(source)
    gaps: list[dict[str, Any]] = []
    if tree.root_node.has_error:
        gaps.append({'file': path, 'reason': 'javascript_parse_partial'})
    items: list[dict[str, Any]] = []
    pending = [tree.root_node]
    while pending:
        node = pending.pop()
        pending.extend(reversed(node.named_children))
        if node.type not in FUNCTIONS:
            continue
        first = source.count(b'\n', 0, node.start_byte) + 1
        last = source.count(b'\n', 0, node.end_byte) + 1
        name_node = node.child_by_field_name('name')
        name = source[name_node.start_byte:name_node.end_byte].decode() if name_node is not None else ''
        if not name and node.parent is not None:
            parent = node.parent
            field = ('name' if parent.type == 'variable_declarator' else
                     'left' if parent.type == 'assignment_expression' else 'key')
            bound = parent.child_by_field_name(field)
            if bound is not None:
                name = source[bound.start_byte:bound.end_byte].decode()
        name = name or '<anonymous>'
        items.append({'file': path, 'symbol': name,
                      'qualified_name': f'{path}::{name}@{node.start_byte}:{node.end_byte}',
                      'label': 'Method' if node.type == 'method_definition' else 'Function',
                      'start_line': first, 'end_line': last,
                      'start_byte': node.start_byte, 'end_byte': node.end_byte,
                      'source': source[node.start_byte:node.end_byte].decode()})
    return {'items': items, 'gaps': gaps}
