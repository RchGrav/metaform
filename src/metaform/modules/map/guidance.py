"""Editable guidance for construction on an existing map."""
from __future__ import annotations

from typing import Any

from metaform import prompt_files
from metaform.module import Context, prepare_agent_context

URI = 'metaform://map/construction'
NAME = 'prompt.map:construction_guide'


def construction_component(ctx: Context) -> dict[str, Any]:
    """Resolve the selected guide without interpreting the intake task's instructions."""
    component = prompt_files.resolve(NAME)
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
