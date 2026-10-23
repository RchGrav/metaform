"""Existing-map construction guidance derived from the untouched intake sources.

The served Axiom supplies normative construction constraints. The original XML
supplies its fuller definitions, namespace rules and valid/invalid examples;
its identity is recorded separately rather than treating the two as one text.
"""
from __future__ import annotations

import hashlib
import re
from importlib import resources
from typing import Any

from metaform import prompt_files
from metaform.module import Context, prepare_agent_context

URI = 'metaform://map/construction'
NAME = 'prompt.map:construction_guide'
INTAKE = resources.files('metaform') / 'modules' / 'intake' / 'resources'
AXIOM_SECTIONS = (
    '@CONSTRAINT:',
    '@CONDITION (NS_VALID)',
    '@CONDITION (CQU_VALID)',
    '@CONDITION (ROLE_ASSIGN)',
    '@CONDITION (ENCAPSULATE)',
)
CONCEPTS = ('AUE', 'OP', 'EF', 'RE', 'CQU', 'PE', 'AT', 'DE', 'SE', 'NE', 'Parametric', 'IFD')


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _block(text: str, marker: str) -> str:
    start = text.index(marker)
    following = text.find('\n@', start + len(marker))
    return text[start:following if following >= 0 else len(text)].rstrip()


def _xml_section(text: str, name: str) -> str:
    start = text.index(f'<{name}>')
    return text[start:text.index(f'</{name}>', start) + len(name) + 3]


def construction_component(ctx: Context) -> dict[str, Any]:
    """Resolve the selected wrapper and exact source excerpts; this establishes no delivery receipt."""
    axiom = (INTAKE / 'intake.axiom').read_bytes().decode('utf-8')
    xml = (INTAKE / 'intake.xml').read_bytes().decode('utf-8')
    axiom_digest, xml_digest = _digest(axiom), _digest(xml)
    declarations = '\n'.join(line for line in axiom.splitlines()
                             if any(line.lstrip().startswith('{' + name + '}')
                                    for name in ('Roots', 'Roles', 'Purpose_Types', 'IFD')))
    invariant = next(line.strip() for line in _block(axiom, '@EXECUTE_PIPELINE (Trace)').splitlines()
                     if '[INVARIANT]:' in line)
    normative = '\n\n'.join((declarations, *(_block(axiom, marker) for marker in AXIOM_SECTIONS), invariant))
    concepts: list[str] = []
    for term in CONCEPTS:
        found = re.search(r'<concept\s+term="' + re.escape(term) + r'"\s[^>]+/>', xml)
        if found is None:
            raise ValueError(f'intake.xml has no definition for {term}.')
        concepts.append(found.group(0))
    definitions = '\n'.join(concepts)
    component = prompt_files.resolve(NAME,
        canonical_source=f'intake.axiom (SHA-256 {axiom_digest})',
        reference_source=f'intake.xml (SHA-256 {xml_digest})',
        normative=normative, definitions=definitions, namespace_rules=_xml_section(xml, 'namespace_rules'),
        cqu_rules=_xml_section(xml, 'cqu_entity_rules'))
    # Retain source identities rather than repeating complete source bodies in receipt bindings.
    component['bindings'] = {'canonical_source_sha256': axiom_digest, 'xml_reference_sha256': xml_digest}
    component['source'] = {'kind': 'derived', 'wrapper': component['source'],
        'canonical': {'path': str(INTAKE / 'intake.axiom'), 'sha256': axiom_digest,
                      'sections': list(AXIOM_SECTIONS), 'declarations': ['Roots', 'Roles', 'Purpose_Types', 'IFD'],
                      'trace_invariant': True},
        'reference': {'path': str(INTAKE / 'intake.xml'), 'sha256': xml_digest,
                      'sections': ['namespace_rules', 'cqu_entity_rules'], 'concepts': list(CONCEPTS)}}
    component['read'] = {'uri': URI}
    return component


def guide(ctx: Context) -> str:
    """The CLI and explicit MCP resource return the same complete current guide."""
    component = construction_component(ctx)
    prepared = prepare_agent_context(ctx.folder, ctx.session, [component], project=ctx.project)
    ctx.queue_context([component], int(prepared['epoch']))
    return str(component['text'])


def instructions(ctx: Context, tool: str, op: str | None) -> list[dict[str, Any]]:
    """Contribute construction guidance to actual construction tools, without restricting their availability."""
    if tool not in ('map_refine', 'map_knowledge', 'map_promote'):
        return []
    return [construction_component(ctx)]
