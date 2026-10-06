"""Requester records live in the shared chassis data service."""
from metaform import data
from metaform.namespace_objects import JoinRef
from metaform.objects import Record


def save_request(prompt: str) -> Record:
    return data.put('data.event_requester.request', {'prompt': prompt, 'joins': {}})


async def save_response(source: JoinRef, event_id: str, nonce: str | None) -> Record:
    record = await data.aresolve(source)
    if record is None:
        raise LookupError(f'Unknown harness response: {source}')
    return await data.aput('data.event_requester.response', {
        'response': source.namespace_address, 'revision': record['record_revision'],
        'response_ref': source,
        'event': event_id, 'nonce': nonce, 'answer': record['content']['answer'], 'joins': {},
        'status': record['content']['status'],
        'request_ref': record['content']['request_ref'],
        'error': record['content'].get('error'),
    })
