"""The image's health check: the service this container runs, named by METAFORM_NODE_SERVICE, answers on loopback.

Docker runs it every 30 seconds; compose starts mcp and web only once auth is healthy, since they need the
introspection credential auth writes on its first start.
"""
from __future__ import annotations

import http.client
import os
import sys

from .config import AUTH_PORT, GATE_PORT, MCP_PORT, WEB_PORT

# Each service's port and a path it answers without credentials, with the statuses that mean it is up.
CHECKS = {'auth': (AUTH_PORT, '/node/health', (200,)),
          'mcp': (MCP_PORT, '/.well-known/oauth-protected-resource/mcp', (200,)),
          'web': (WEB_PORT, '/', (200, 302, 401, 403)),
          'gate': (GATE_PORT, '/health', (200,))}


def healthy(service: str) -> bool:
    port, path, good = CHECKS[service]
    connection = http.client.HTTPConnection('127.0.0.1', port, timeout=4)
    try:
        connection.request('GET', path, headers={'Host': f'127.0.0.1:{port}'})
        return connection.getresponse().status in good
    except OSError:
        return False
    finally:
        connection.close()


def main() -> int:
    service = os.environ.get('METAFORM_NODE_SERVICE', '')
    if service not in CHECKS:
        print(f'METAFORM_NODE_SERVICE is {service!r}; expected one of {", ".join(CHECKS)}', file=sys.stderr)
        return 1
    return 0 if healthy(service) else 1


if __name__ == '__main__':
    sys.exit(main())
