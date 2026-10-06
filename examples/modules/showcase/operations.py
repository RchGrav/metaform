"""Registered operations and background work using public chassis services."""
import asyncio
from metaform import cli, data, event, modules, settings, work
from metaform.namespace_objects import JoinRef, NamespaceRef
from metaform.objects import Assignment, Job
from . import dao
from .dao import inspect
from .events import watch

def write(text: str, address: str = 'data.showcase.note') -> JoinRef:
    reference = dao.save(address, text, settings.get('label'))
    event.publish(cli.context().module + '.saved', refs=(reference,))
    return reference


def annotate(text: str, join_id: str | None = None) -> JoinRef:
    reference = dao.annotate(text, join_id)
    event.publish(cli.context().module + '.saved', refs=(reference,))
    return reference


def author(answer: str, source: JoinRef | None = None, prompt: JoinRef | None = None,
           source_revision: int | None = None, prompt_revision: int | None = None) -> JoinRef:
    """Demonstrate a fixed rendering and authored answer with exact object inputs."""
    source = source or dao.reference('data.showcase.note', 'note', source_revision)
    prompt = prompt or dao.reference('document.showcase.prompt', 'instruction', prompt_revision)
    namespaces = data.namespace_store()
    source_body, prompt_body = namespaces.resolve(source), namespaces.resolve(prompt)
    if source_body is None or prompt_body is None:
        raise ValueError('The exact source and prompt revisions must exist')
    rendered = prompt_body['text'] + '\n\nRecorded note:\n' + source_body['text']
    return dao.authored_answer(answer, source, prompt, rendered)


async def delayed(text: str, seconds: float = 1.0,
                  address: str = 'data.showcase.async') -> JoinRef:
    await asyncio.sleep(seconds)
    reference = await dao.asave(address, text, await settings.aget('label'))
    await event.apublish(cli.context().module + '.saved', refs=(reference,))
    return reference


def queue(text: str, seconds: float = 1.0) -> Job:
    return work.submit_job('delayed', text=text, seconds=seconds)


def assignment(prompt: str = 'Write an observation about the project. Preserve your answer as supplied.') -> Assignment:
    prompt_ref = dao.assignment_prompt(prompt)
    source = data.namespace_store().latest_ref('data.showcase.note', 'note')
    return work.assign(prompt, knowledge=(source,) if source else (),
                       prompt_revision=prompt_ref, inputs=[prompt_ref])


def features() -> dict:
    return {
        'module': modules.describe(cli.context().module),
        'context': cli.context(),
        'settings': settings.describe(),
        'loaded_modules': modules.catalog(),
        'objects': [NamespaceRef(cli.context().project, obj.namespace_address)
                    for scope in ('data.showcase', 'document.showcase')
                    for obj in data.namespace_store().list(scope)],
        'jobs': work.jobs(),
        'events': event.history(),
        'actions': {
            'sample-write --text TEXT': 'Sync operation, owned join, revision, producer and event',
            'sample-read [--revision N]': 'Read an exact join and its producing occurrences',
            'sample-join --text TEXT [--join-id ID]': 'Create or revise an owned join and publish its exact reference',
            'sample-prompt --text TEXT': 'Retain or revise the authored instruction for this example',
            'sample-author --answer TEXT': 'Retain an authored answer, exact prompt, bindings and inputs',
            'sample-async --text TEXT --seconds 2': 'Background async job; use jobs to inspect or cancel',
            'sample-assignment [--prompt TEXT]': 'Issue nonce, exact instructions and submission header',
            'sample-watch --on/--off': 'Register or remove a dynamic subscription',
            'settings': 'Inspect module settings and conditional command availability',
            'events': 'Inspect persisted publications and per-handler delivery outcomes',
            'namespace': 'Inspect project-owned objects and their retained joins',
            'exit': 'Leave the module menu and restore the base commands',
        },
    }


OPERATIONS = {
    'features': features, 'write': write, 'inspect': inspect,
    'annotate': annotate, 'prompt': dao.prompt, 'author': author,
    'delayed': delayed, 'queue': queue, 'assignment': assignment, 'watch': watch,
}
