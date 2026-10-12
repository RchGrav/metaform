"""The tunnel's wire format, shared by the broker (node/broker.py) and the local service (tunnel.py).

The local service opens one WebSocket to `wss://<cloud>/cloud/tunnel`, subprotocol `metaform-tunnel.1`, and every
message on it is one binary frame: a 4-byte big-endian length, that many bytes of JSON header, then the body's raw
bytes. The broker numbers a stream for each HTTP request an AI host makes (the hosts' JSON-RPC ids are theirs and
collide across hosts, so they never key anything here).

| type     | from   | header                                                         | body                     |
|----------|--------|----------------------------------------------------------------|--------------------------|
| hello    | local  | version, instance, allows (the scopes this machine grants)      | none                     |
| ready    | broker | account, instance, resource (the URL hosts use), limits         | none                     |
| auth     | local  | token, proof: a fresh access token and DPoP proof, before expiry | none                     |
| open     | broker | stream, method, path, query, headers (allowlisted), assertion   | the request body, whole  |
| head     | local  | stream, status, headers (allowlisted)                           | none                     |
| data     | local  | stream                                                         | response bytes, SSE too  |
| end      | local  | stream, error (optional)                                       | none                     |
| cancel   | both   | stream, reason                                                 | none                     |
| credit   | broker | stream, bytes                                                  | none                     |
| goaway   | broker | reason, reconnect_after_ms                                     | none                     |

The local service sends `data` only while it holds credit for the stream, 256 KiB to start, given back by the broker
as the host reads, so one slow host stalls only its own stream.
"""
from __future__ import annotations

import json
import struct
from typing import Any, cast

VERSION = 1
SUBPROTOCOL = 'metaform-tunnel.1'
TYPES = frozenset({'hello', 'ready', 'auth', 'open', 'head', 'data', 'end', 'cancel', 'credit', 'goaway'})
MAX_HEADER = 64 * 1024
MAX_FRAME_BODY = 1024 * 1024
CREDIT = 256 * 1024

# Close codes. 4001: the token is no longer valid, refresh it and reconnect; 4003: the account signed out everywhere or
# the grant was revoked, sign in again; 4008: a frame too large; 4009: a newer connection for the same instance took its
# place; 4029: too many connections, back off; 1012: the broker is restarting, reconnect after goaway's delay.
INVALID_TOKEN, REVOKED, TOO_LARGE, REPLACED, RATE_LIMITED, RESTARTING = 4001, 4003, 4008, 4009, 4029, 1012

# Headers carried across, each way; never authorization, cookies, host, origin or forwarding headers. An answer's
# WWW-Authenticate is carried back, so a host told insufficient_scope can step up at the broker.
REQUEST_HEADERS = ('content-type', 'accept', 'mcp-method', 'mcp-name', 'mcp-protocol-version', 'mcp-session-id',
                   'last-event-id')


def response_header(name: str) -> bool:
    lowered = name.lower()
    return lowered in ('content-type', 'cache-control', 'www-authenticate') or lowered.startswith('mcp-')


def pack(header: dict[str, Any], body: bytes = b'') -> bytes:
    if header.get('type') not in TYPES:
        raise ValueError(f'Unknown frame type {header.get("type")!r}.')
    encoded = json.dumps(header, separators=(',', ':')).encode()
    return struct.pack('>I', len(encoded)) + encoded + body


def unpack(frame: bytes) -> tuple[dict[str, Any], bytes]:
    """A frame's header and body; ValueError for anything that is not one."""
    if len(frame) < 4:
        raise ValueError('A frame shorter than its length prefix.')
    (size,) = struct.unpack('>I', frame[:4])
    if size > MAX_HEADER or 4 + size > len(frame):
        raise ValueError('A frame header longer than allowed or than the frame.')
    header: Any = json.loads(frame[4:4 + size])
    if not isinstance(header, dict) or cast(dict[str, Any], header).get('type') not in TYPES:
        raise ValueError('A frame header that is not a known frame.')
    return cast(dict[str, Any], header), frame[4 + size:]
