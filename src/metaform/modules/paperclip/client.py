"""A client for Paperclip's control-plane REST API, the calls this module makes and no others.

Paperclip (github.com/paperclipai/paperclip) serves a JSON API under `/api` (docs/api/overview.md there): a bearer
token in `Authorization`, an agent's run id in `X-Paperclip-Run-Id` on every mutating request made during a heartbeat,
`{"error": "..."}` on failure, and `409` when another agent owns a task, which is never retried. The paths and bodies
below are those of docs/api/issues.md, agents.md and its MCP server's client (packages/mcp-server/src). Standard
library only, so the module adds no dependency.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from typing import Any, cast

# Opens one request and returns its response, `urllib.request.urlopen` unless a caller passes its own.
Opener = Callable[..., Any]


class PaperclipError(Exception):
    """A Paperclip call that failed: its method, path, HTTP status (0 when the server was not reached) and the
    server's own error text."""

    def __init__(self, method: str, path: str, status: int, message: str) -> None:
        super().__init__(f'{method} {path} failed{f" with {status}" if status else ""}: {message}')
        self.method, self.path, self.status, self.message = method, path, status, message

    @property
    def owned_elsewhere(self) -> bool:
        """Another agent owns the task: Paperclip's 409 on checkout, which is never retried (docs/api/overview.md)."""
        return self.status == 409


def base_url(url: str) -> str:
    """The server's origin as Paperclip writes PAPERCLIP_API_URL, `http://localhost:3100`, with any `/api` dropped."""
    url = url.strip().rstrip('/')
    return url.removesuffix('/api')


class Client:
    """One Paperclip server, reached as one caller: a board key, an agent key or a heartbeat's run token, or no token
    for a server in local_trusted mode, which treats every request as the local board (docs/api/authentication.md)."""

    def __init__(self, url: str, token: str | None = None, *, run_id: str | None = None, timeout: float = 30.0,
                 opener: Opener | None = None) -> None:
        self.url = base_url(url)
        self.token = token or None
        self.run_id = run_id or None
        self.timeout = timeout
        self._open: Opener = opener or urllib.request.urlopen

    def request(self, method: str, path: str, body: Any = None, *, query: Mapping[str, Any] | None = None) -> Any:
        """One call under `/api`: its JSON answer, None for an empty one; PaperclipError on any failure."""
        given = {key: value for key, value in (query or {}).items() if value not in (None, '')}
        target = f'{self.url}/api{path}' + (f'?{urllib.parse.urlencode(given)}' if given else '')
        headers = {'Accept': 'application/json'}
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'
        if method != 'GET' and self.run_id:
            headers['X-Paperclip-Run-Id'] = self.run_id
        data = None
        if body is not None:
            data = json.dumps(body).encode('utf-8')
            headers['Content-Type'] = 'application/json'
        request = urllib.request.Request(target, data=data, method=method, headers=headers)
        try:
            with self._open(request, timeout=self.timeout) as response:
                text = response.read().decode('utf-8')
        except urllib.error.HTTPError as error:
            raise PaperclipError(method, path, error.code, _error_text(error.read().decode('utf-8', 'replace'),
                                                                       str(error.reason))) from None
        except (urllib.error.URLError, OSError) as error:
            reason = getattr(error, 'reason', error)
            raise PaperclipError(method, path, 0, f'{self.url} was not reached ({reason})') from None
        return json.loads(text) if text.strip() else None

    # ------------------------------------------------------------------ reads

    def health(self) -> Any:
        return self.request('GET', '/health')

    def me(self) -> Any:
        """The calling agent: id, company, role, chain of command and budget. 401 for a board caller."""
        return self.request('GET', '/agents/me')

    def issue(self, issue_id: str) -> Any:
        return self.request('GET', f'/issues/{_part(issue_id)}')

    def issues(self, company_id: str, *, status: str | None = None, assignee: str | None = None,
               project: str | None = None) -> Any:
        return self.request('GET', f'/companies/{_part(company_id)}/issues',
                            query={'status': status, 'assigneeAgentId': assignee, 'projectId': project})

    def inbox(self) -> Any:
        """The calling agent's compact assignment list, todo, in_progress and blocked: id, identifier, title, status
        and more, but no description; 401 for a board caller (server/src/routes/agents.ts, GET /agents/me/inbox-lite,
        the heartbeat inbox skills/paperclip/SKILL.md prefers)."""
        return self.request('GET', '/agents/me/inbox-lite')

    def agents(self, company_id: str) -> Any:
        """Every agent of the company: id, name, urlKey, role, title, capabilities, adapterType and status."""
        return self.request('GET', f'/companies/{_part(company_id)}/agents')

    def comments(self, issue_id: str, after: str | None = None, limit: int = 100) -> Any:
        """The issue's comments oldest first, those after the comment `after` when given (server/src/routes/issues.ts,
        GET /issues/:id/comments, `after`, `order`, `limit`)."""
        return self.request('GET', f'/issues/{_part(issue_id)}/comments',
                            query={'after': after, 'order': 'asc', 'limit': limit})

    def document(self, issue_id: str, key: str) -> Any:
        """The issue's document under this key, or None when it has none."""
        try:
            return self.request('GET', f'/issues/{_part(issue_id)}/documents/{_part(key)}')
        except PaperclipError as error:
            if error.status == 404:
                return None
            raise

    def interactions(self, issue_id: str) -> Any:
        """The issue's thread interactions, question and confirmation cards, each with its status and result
        (server/src/routes/issues.ts, GET /issues/:id/interactions)."""
        return self.request('GET', f'/issues/{_part(issue_id)}/interactions')

    # ------------------------------------------------------------------ writes

    def create_issue(self, company_id: str, fields: Mapping[str, Any]) -> Any:
        """A new issue. An `idempotencyKey` field makes a second create with the same key replay the first issue."""
        return self.request('POST', f'/companies/{_part(company_id)}/issues', dict(fields))

    def update_issue(self, issue_id: str, fields: Mapping[str, Any]) -> Any:
        """Change an issue; a `comment` field adds a comment in the same call."""
        return self.request('PATCH', f'/issues/{_part(issue_id)}', dict(fields))

    def checkout(self, issue_id: str, agent_id: str, expected: tuple[str, ...]) -> Any:
        """Claim the issue for the agent, moving it to in_progress; 409 when another agent owns it."""
        return self.request('POST', f'/issues/{_part(issue_id)}/checkout',
                            {'agentId': agent_id, 'expectedStatuses': list(expected)})

    def release(self, issue_id: str) -> Any:
        """Give up this agent's claim on the issue."""
        return self.request('POST', f'/issues/{_part(issue_id)}/release')

    def comment(self, issue_id: str, body: str, request_id: str | None = None) -> Any:
        """Add a comment. `request_id`, a UUID, is Paperclip's `clientRequestId`: a retry with the same one is the
        same comment (packages/shared/src/validators/issue.ts, addIssueCommentSchema)."""
        given: dict[str, Any] = {'body': body}
        if request_id:
            given['clientRequestId'] = request_id
        return self.request('POST', f'/issues/{_part(issue_id)}/comments', given)

    def ask(self, issue_id: str, fields: Mapping[str, Any]) -> Any:
        """A thread interaction on the issue, such as ask_user_questions; an `idempotencyKey` field makes a repeat the
        same interaction (packages/shared/src/validators/issue.ts, createIssueThreadInteractionSchema). An agent caller
        needs the run id header."""
        return self.request('POST', f'/issues/{_part(issue_id)}/interactions', dict(fields))

    def withdraw(self, issue_id: str, interaction_id: str) -> Any:
        """Withdraw a pending interaction this caller made (POST /issues/:id/interactions/:interactionId/withdraw;
        its reason is optional, withdrawIssueThreadInteractionSchema)."""
        return self.request('POST', f'/issues/{_part(issue_id)}/interactions/{_part(interaction_id)}/withdraw', {})

    def put_document(self, issue_id: str, key: str, title: str, body: str, base_revision: str | None) -> Any:
        """Create the issue's document under this key, or update it from the revision last read."""
        given: dict[str, Any] = {'title': title, 'format': 'markdown', 'body': body}
        if base_revision:
            given['baseRevisionId'] = base_revision
        return self.request('PUT', f'/issues/{_part(issue_id)}/documents/{_part(key)}', given)


def _part(value: str) -> str:
    return urllib.parse.quote(str(value), safe='')


def _error_text(body: str, fallback: str) -> str:
    try:
        found = json.loads(body)
    except ValueError:
        return body.strip()[:200] or fallback
    error = cast(dict[str, Any], found).get('error') if isinstance(found, dict) else None
    return error if isinstance(error, str) else fallback
