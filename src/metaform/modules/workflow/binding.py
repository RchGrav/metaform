"""Argument and return transport for Axiom's agent interpreter, MAP-056.

This reads the call boundary. The subroutine's authored instructions remain
verbatim; the agent interprets its pipelines, conditions and verification.
"""
from __future__ import annotations

import ast
import io
import re
import tokenize
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, cast

from metaform.data import Record


@dataclass(frozen=True)
class Logic(Record):
    type: str
    logic_id: str
    name: str
    content: str


@dataclass(frozen=True)
class Call(Record):
    address: str
    logic: Logic
    arguments: dict[str, Any]
    this: Any
    targets: tuple[str, ...]
    unpack: bool


Lookup = Callable[[str, str], tuple[Logic, Any]]
PARAM = re.compile(r'^\s*\{(\w+)\}\s*:=\s*PARAM(?:\s*=\s*(.*))?$')


def _expression(text: str) -> ast.expr:
    return ast.parse(text.strip(), mode='eval').body


def _value(node: ast.expr, variables: Mapping[str, Any], this: Any,
           resolve: Callable[[str], Any] | None = None) -> Any:
    """Read data expressions without executing Python supplied in a prompt."""
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        if node.id == 'this':
            return this
        if node.id in ('NULL', 'TRUE', 'FALSE'):
            return {'NULL': None, 'TRUE': True, 'FALSE': False}[node.id]
        return variables[node.id]
    if isinstance(node, ast.Set) and len(node.elts) == 1:
        return _value(node.elts[0], variables, this, resolve)  # Axiom's {variable}
    if isinstance(node, ast.Attribute):
        if resolve is not None:
            try:
                address = _address(node)
            except TypeError:
                address = ''
            if address and address.partition('.')[0] not in variables:
                return resolve(address)
        return getattr(_value(node.value, variables, this, resolve), node.attr)
    if isinstance(node, ast.Subscript):
        return _value(node.value, variables, this, resolve)[_value(node.slice, variables, this, resolve)]
    if isinstance(node, (ast.List, ast.Tuple)):
        values = [_value(one, variables, this, resolve) for one in node.elts]
        return tuple(values) if isinstance(node, ast.Tuple) else values
    if isinstance(node, ast.Dict):
        return {_value(key, variables, this, resolve): _value(value, variables, this, resolve)
                for key, value in zip(node.keys, node.values) if key is not None}
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        value = _value(node.operand, variables, this, resolve)
        return -value if isinstance(node.op, ast.USub) else +value
    if isinstance(node, ast.Call) and not node.keywords:
        args = [_value(one, variables, this, resolve) for one in node.args]
        if isinstance(node.func, ast.Name) and node.func.id == 'len' and len(args) == 1:
            return len(args[0])
        if isinstance(node.func, ast.Attribute) and node.func.attr == 'get':
            return _value(node.func.value, variables, this, resolve).get(*args)
    if isinstance(node, ast.Compare):
        left = _value(node.left, variables, this, resolve)
        for op, right_node in zip(node.ops, node.comparators):
            right = _value(right_node, variables, this, resolve)
            if isinstance(op, ast.Eq):
                matches = left == right
            elif isinstance(op, ast.NotEq):
                matches = left != right
            else:
                raise TypeError('This data comparison is not supported.')
            if not matches:
                return False
            left = right
        return True
    if isinstance(node, ast.ListComp) and len(node.generators) == 1:
        generator = node.generators[0]
        if isinstance(generator.target, ast.Name) and not generator.is_async:
            values: list[Any] = []
            for one in _value(generator.iter, variables, this, resolve):
                scope = {**variables, generator.target.id: one}
                if all(_value(condition, scope, this, resolve) for condition in generator.ifs):
                    values.append(_value(node.elt, scope, this, resolve))
            return values
    raise TypeError(f'Not a data expression: {ast.unparse(node)}')


def _without_comment(line: str) -> str:
    """A # inside a quoted default is data, not an Axiom comment."""
    for token in tokenize.generate_tokens(io.StringIO(line).readline):
        if token.type == tokenize.COMMENT:
            return line[:token.start[1]]
    return line


def parameters(content: str, arguments: Mapping[str, Any], this: Any) -> dict[str, Any]:
    values: dict[str, Any] = {}
    in_state = False
    for line in content.splitlines():
        if line.strip().startswith('@'):
            in_state = line.strip().startswith('@STATE_INIT:')
            continue
        if not in_state or not re.match(r'\s*\{\w+\}\s*:=\s*PARAM\b', line):
            continue
        match = PARAM.fullmatch(_without_comment(line).rstrip())
        if match is None:
            continue
        name, default = match.groups()
        given = arguments.get(name)
        if given is None:
            if default is None:
                raise TypeError(f'Missing required parameter: {name}')
            given = _value(_expression(default), values, this)
        values[name] = given
    unknown = arguments.keys() - values.keys()
    if unknown:
        raise TypeError(f'Unknown keyword arguments: {", ".join(sorted(unknown))}')
    return values


def _address(node: ast.expr) -> str:
    if isinstance(node, ast.Name) and node.id != 'this':
        return node.id
    if isinstance(node, ast.Attribute):
        return _address(node.value) + '.' + node.attr
    raise TypeError('A call names an element address and a subroutine name.')


def _targets(text: str) -> tuple[tuple[str, ...], bool]:
    node = _expression(text)
    entries = node.elts if isinstance(node, ast.Tuple) else [node]
    names: list[str] = []
    for entry in entries:
        if isinstance(entry, ast.Set) and len(entry.elts) == 1:
            entry = entry.elts[0]
        if not isinstance(entry, ast.Name) or entry.id == 'this':
            raise TypeError('Return targets are caller variables.')
        names.append(entry.id)
    return tuple(names), isinstance(node, ast.Tuple)


def _call_expression(text: str) -> tuple[tuple[str, ...], bool, ast.Call]:
    targets: tuple[str, ...] = ()
    unpack = False
    expression = text
    for token in tokenize.generate_tokens(io.StringIO(text).readline):
        if token.type == tokenize.OP and token.string == ':=':
            offset = sum(len(line) for line in text.splitlines(keepends=True)[:token.start[0] - 1]) + token.start[1]
            targets, unpack = _targets(text[:offset])
            expression = text[offset + 2:]
            break
    node = _expression(expression)
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
        raise TypeError('A call names an element address and a subroutine name.')
    return targets, unpack, node


def destination(text: str) -> tuple[str, str]:
    """Locate a call before loading its selected knowledge and binding arguments."""
    _, _, node = _call_expression(text)
    function = cast(ast.Attribute, node.func)
    return _address(function.value), function.attr


def prepare(text: str, variables: Mapping[str, Any], this: Any, lookup: Lookup,
            resolve: Callable[[str], Any] | None = None) -> Call:
    targets, unpack, node = _call_expression(text)
    function = cast(ast.Attribute, node.func)
    address, name = _address(function.value), function.attr
    if node.args or any(keyword.arg is None for keyword in node.keywords):
        raise TypeError('Subroutine arguments are by keyword.')
    arguments: dict[str, Any] = {}
    for keyword in node.keywords:
        key = cast(str, keyword.arg)
        if key in arguments:
            raise TypeError(f'Duplicate keyword argument: {key}')
        arguments[key] = _value(keyword.value, variables, this, resolve)
    logic, owner = lookup(address, name)
    return Call(address, logic, parameters(logic.content, arguments, owner), owner, targets, unpack)


def returned(text: str, variables: Mapping[str, Any], this: Any) -> Any:
    prefix, separator, expression = text.strip().partition(' ')
    if prefix != 'RETURN' or not separator:
        raise TypeError('Expected RETURN followed by a value or tuple.')
    return _value(_expression(expression), variables, this)


def receive(call: Call, value: Any, variables: Mapping[str, Any]) -> dict[str, Any]:
    """Return a new caller scope; return values are never stored implicitly."""
    if not call.targets:
        return dict(variables)
    values = tuple(value) if call.unpack else (value,)
    if len(values) != len(call.targets):
        raise ValueError(f'Expected {len(call.targets)} return values, got {len(values)}.')
    return {**variables, **dict(zip(call.targets, values))}
