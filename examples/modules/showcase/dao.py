"""Module-owned joins using the chassis' shared object and revision services."""
from metaform import data
from metaform.namespace_objects import JoinRef
from .models import JoinInspection, ProductionInspection


def save(address: str, text: str, label: str) -> JoinRef:
    return data.namespace_store().put_join(address, {
        'id': 'note', 'type': 'example.note', 'origin': 'authored',
        'text': text, 'label': label,
    })


async def asave(address: str, text: str, label: str) -> JoinRef:
    return await data.namespace_store().aput_join(address, {
        'id': 'note', 'type': 'example.note', 'origin': 'authored',
        'text': text, 'label': label,
    })


def reference(address: str, join_id: str, revision: int | None = None) -> JoinRef:
    current = data.namespace_store().latest_ref(address, join_id)
    if current is None:
        raise ValueError(f'No {join_id} join at {address}')
    return current if revision is None else JoinRef(
        current.project, address, join_id, revision)


def inspect(address: str = 'data.showcase.note', revision: int | None = None,
            join_id: str = 'note', reference: JoinRef | None = None) -> JoinInspection:
    """Follow an exact output to every retained producing occurrence."""
    namespaces = data.namespace_store()
    if reference is None:
        current = namespaces.latest_ref(address, join_id)
        if current is None:
            return {'reference': None, 'join': None, 'productions': []}
        reference = current if revision is None else JoinRef(
            current.project, address, join_id, revision)
    body = namespaces.resolve(reference)
    if body is None:
        return {'reference': reference, 'join': None, 'productions': []}
    owner = namespaces.get(reference.namespace_address, ['provenance'])
    productions: list[ProductionInspection] = [
        {'reference': join['producer'], 'production': namespaces.resolve(join['producer'])}
        for join in owner.joins.values() if join['output'] == reference
    ]
    return {'reference': reference, 'join': body, 'productions': productions}


def annotate(text: str, join_id: str | None = None) -> JoinRef:
    """Attach a typed join with its exact source; chassis owns its revision."""
    source = reference('data.showcase.note', 'note')
    data.namespace_store().resolve(source)
    join = {'type': 'example.note', 'text': text, 'source': source}
    if join_id is not None:
        join['id'] = join_id
    return data.namespace_store().put_join('document.showcase.note', join, name_length=2)


def prompt(text: str) -> JoinRef:
    """Retain the supplied instruction; repeating this edits the same prompt."""
    return data.namespace_store().put_join('document.showcase.prompt', {
        'id': 'instruction', 'type': 'example.prompt', 'origin': 'authored', 'text': text,
    })


def assignment_prompt(text: str) -> JoinRef:
    return data.namespace_store().put_join('document.showcase.assignment', {
        'type': 'example.prompt', 'origin': 'authored', 'text': text,
    })


def authored_answer(answer: str, source: JoinRef, prompt: JoinRef,
                    rendered_prompt: str) -> JoinRef:
    return data.namespace_store().put_join('document.showcase.answer', {
        'type': 'example.authored', 'origin': 'authoring-demonstration',
        'prompt': prompt, 'rendered_prompt': rendered_prompt,
        'bindings': {'source': source}, 'inputs': [source, prompt],
        'selected_layers': [], 'answer': answer,
    })


def receipt(address: str, event_id: str, refs: list[object]) -> JoinRef:
    return data.namespace_store().put_join(address, {
        'id': 'latest', 'type': 'example.receipt', 'event': event_id, 'refs': refs,
    })


async def areceipt(address: str, event_id: str, refs: list[object]) -> JoinRef:
    return await data.namespace_store().aput_join(address, {
        'id': 'latest', 'type': 'example.receipt', 'event': event_id, 'refs': refs,
    })
