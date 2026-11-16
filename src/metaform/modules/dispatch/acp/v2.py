"""The ACP v2 adapter: v2's wire shapes, capabilities, validation and lifecycle, behind the model.

v2 is the protocol's draft (agentclientprotocol.com, protocol/v2 and its migration guide). What it changes from v1,
and how it reaches the model:

- `initialize` carries `info` and one `capabilities` object, with support markers as objects; once a harness offers
  sessions, list, resume (with or without replay) and close are always there. A harness that knows only v1 selects 1,
  which is told as `SelectedVersion`, and the connection starts it again in v1.
- `session/prompt` answers once the message is inserted, with its id; the work's progress and end are
  `state_update`s, and the stop reason is on the idle one. A prompt's work ends at the first idle after it began.
- messages, tool calls, plans and display terminals are upserts by id: left out is unchanged, null clears, a value
  replaces, chunks append; a top-level `_meta` is patched by key.
- modes are config options; `session/set_config_option` carries a `type`.
- `session/load` is `session/resume` with `replayFrom`, and the replay ends with `replay_complete`.
- the client's own files and terminals are gone; client tools are MCP servers given at session setup.

The adapter speaks v2's JSON over the SDK's JSON-RPC connection (`acp.connection.Connection`) rather than through the
SDK's typed v2 client (`acp.experimental.v2`, 1.0.0rc2): that client validates updates into models that cannot tell
a field left out from one set to null, which v2's upserts depend on; it has no `systemPrompt` or `configOptions` on
session setup; and it closes the connection when a harness selects 1, where the version evidence is wanted.
"""
from __future__ import annotations

import base64
import binascii
from typing import Any, cast

from acp.exceptions import RequestError

from .model import (
    ACTIVE,
    COMMANDS,
    COMPACTION,
    IDLE,
    INFO,
    INVALID,
    MESSAGE,
    NOTICE,
    OPTIONS,
    OTHER,
    PLAN,
    REPLAY,
    TERMINAL,
    TOOL_CALL,
    TURN,
    USAGE,
    Capabilities,
    ConfigOption,
    Harness,
    Login,
    McpServer,
    Message,
    Offer,
    OptionValue,
    PermissionOption,
    PermissionRequest,
    Plan,
    Prompt,
    SelectedVersion,
    SessionSetup,
    SessionState,
    SystemPrompt,
    Terminal,
    ToolCall,
    Turn,
    Unsupported,
    appended,
    command_of,
    dicts,
    meta_patched,
    obj,
    option_of,
    patched,
    text_or_none,
)

UNSUPPORTED_VERSION = -32022  # v2's answer to an initialize asking for a version the agent does not speak
CHUNKS = {'user_message_chunk': 'user', 'agent_message_chunk': 'agent', 'agent_thought_chunk': 'thought'}
WHOLE = {'user_message': 'user', 'agent_message': 'agent', 'agent_thought': 'thought'}


def present(given: dict[str, Any], key: str) -> bool:
    """v2's support marker: an object (`{}`) means supported; left out or null means not."""
    return isinstance(given.get(key), dict)


def evidence(answer: dict[str, Any] | None, error: BaseException | None) -> int | None:
    """The version a harness selected when asked for 2, from the answer or the refusal, when it is not 2: 1 for a v1
    harness (it said 1, or answered in v1's shape, or refused the version and lists 1 or nothing), None otherwise."""
    if answer is not None:
        selected = answer.get('protocolVersion')
        if selected == 1:
            return 1
        if selected == 2 and 'info' not in answer and ('agentInfo' in answer or 'agentCapabilities' in answer):
            return 1  # a v1 agent echoing the version asked for, in v1's shape
        return None
    if isinstance(error, RequestError):
        if error.code == UNSUPPORTED_VERSION:
            versions = obj(error.data).get('supported')
            return 1 if not isinstance(versions, list) or 1 in cast(list[Any], versions) else None
        if error.code in (-32600, -32602) and 'unsupported protocol version' in str(error).lower():
            return 1
    return None


class V2(Harness):
    protocol = 2

    # ------------------------------------------------------------------ initialize

    async def initialize(self, info: dict[str, str], offer: Offer, timeout: float) -> Capabilities:
        capabilities: dict[str, Any] = {}
        if offer.terminal_login:
            capabilities['auth'] = {'terminal': {}}
        if offer.elicitation:
            capabilities['elicitation'] = {'form': {}, 'url': {}}
        try:
            given = await self.request('initialize', {'protocolVersion': 2, 'info': info,
                                                      'capabilities': capabilities}, timeout)
        except RequestError as error:
            selected = evidence(None, error)
            if selected is not None:
                raise SelectedVersion(selected, f'initialize asking for v2 was refused: {error}') from error
            raise
        answer = obj(given)
        if evidence(answer, None) == 1:
            raise SelectedVersion(1, 'the harness selected ACP v1')
        version = answer.get('protocolVersion')
        if version != 2:
            raise SelectedVersion(version if isinstance(version, int) else None,
                                  f'the harness selected ACP protocol {version!r}')
        if not isinstance(answer.get('info'), dict):
            raise RequestError(-32602, 'The harness answered initialize for ACP v2 without its info.')
        self.capabilities = self.read_capabilities(answer, offer)
        return self.capabilities

    def read_capabilities(self, answer: dict[str, Any], offer: Offer) -> Capabilities:
        caps = obj(answer.get('capabilities'))
        session = obj(caps.get('session'))
        prompt, mcp, auth = obj(session.get('prompt')), obj(session.get('mcp')), obj(caps.get('auth'))
        system = session.get('systemPrompt')
        sessions = isinstance(caps.get('session'), dict)
        logins = [Login(method_id=str(one.get('methodId') or ''), name=str(one.get('name') or one.get('methodId')),
                        type=str(one.get('type') or 'agent'), description=text_or_none(one.get('description')),
                        args=[str(arg) for arg in cast(list[Any], one.get('args') or [])],
                        env={str(pair.get('name')): str(pair.get('value') or '') for pair in dicts(one.get('env'))},
                        vars=dicts(one.get('vars')), link=text_or_none(one.get('link')), raw=one)
                  for one in dicts(answer.get('authMethods'))]
        return Capabilities(
            protocol=2, info=obj(answer.get('info')), sessions=sessions, list=sessions, resume=sessions,
            replay=sessions, close=sessions, delete=present(session, 'delete'), fork=present(session, 'fork'),
            options=present(session, 'options'), system_prompt=isinstance(system, dict),
            system_prompt_override=present(obj(obj(system).get('mode')), 'override'),
            image=present(prompt, 'image'), audio=present(prompt, 'audio'),
            embedded_context=present(prompt, 'embeddedContext'), mcp_stdio=present(mcp, 'stdio'),
            mcp_http=present(mcp, 'http'), additional_directories=present(session, 'additionalDirectories'),
            providers=present(caps, 'providers'),
            steering=bool(obj(obj(answer.get('_meta')).get('steering')).get('supported')),
            # Claude Code's adapter says it as auth.status and in _meta; Codex's in auth's _meta
            auth_status=present(auth, 'status') or 'authStatus' in obj(caps.get('_meta'))
            or 'authStatus' in obj(auth.get('_meta')),
            logout=bool(logins), client_files=False, client_terminals=False, terminal_login=offer.terminal_login,
            logins=logins, raw=answer)

    # ------------------------------------------------------------------ sessions

    def setup(self, cwd: str, servers: list[McpServer], directories: list[str] | None,
              options: list[OptionValue] | None, system_prompt: SystemPrompt | None) -> dict[str, Any]:
        caps = self.caps()
        if not caps.sessions:
            raise Unsupported('sessions', 2, 'the harness offers no capabilities.session')
        wired: list[dict[str, Any]] = []
        for server in servers:
            if server.url is not None:
                if not caps.mcp_http:
                    raise Unsupported(f'the MCP server {server.name} over http', 2)
                wired.append({'type': 'http', 'name': server.name, 'url': server.url,
                              'headers': [{'name': key, 'value': value} for key, value in server.headers.items()]})
            else:
                if not caps.mcp_stdio:
                    raise Unsupported(f'the MCP server {server.name} over stdio', 2)
                wired.append({'type': 'stdio', 'name': server.name, 'command': server.command or '',
                              'args': list(server.args),
                              'env': [{'name': key, 'value': value} for key, value in server.env.items()]})
        params: dict[str, Any] = {'cwd': cwd, 'mcpServers': wired}
        if directories:
            if not caps.additional_directories:
                raise Unsupported('additional directories', 2)
            params['additionalDirectories'] = list(directories)
        if options and caps.options:
            params['configOptions'] = [{'configId': one.config_id,
                                        'type': 'boolean' if isinstance(one.value, bool) else 'id',
                                        'value': one.value} for one in options]
        if system_prompt is not None:
            params['systemPrompt'] = self.system_prompt(system_prompt)
        return params

    def system_prompt(self, given: SystemPrompt) -> dict[str, Any]:
        caps = self.caps()
        if not caps.system_prompt:
            raise Unsupported('a system prompt at session setup', 2)
        if given.mode == 'override' and not caps.system_prompt_override:
            raise Unsupported('a system prompt that overrides the harness\'s own', 2)
        if given.mode not in ('append', 'override'):
            raise ValueError(f'A system prompt is appended or overrides, not {given.mode}.')
        return {'mode': given.mode, 'content': [{'type': 'text', 'text': given.text}]}

    def take(self, session_id: str, answer: dict[str, Any]) -> SessionSetup:
        state = self.session(session_id)
        named = isinstance(answer.get('configOptions'), list)
        if named:
            state.options = [option_of(one, 'configId', 'groupId') for one in dicts(answer['configOptions'])]
            self.tell(session_id, OPTIONS, '', state.options, raw=answer)
        if isinstance(answer.get('availableCommands'), list):
            state.commands = [command_of(one) for one in dicts(answer['availableCommands'])]
            self.tell(session_id, COMMANDS, '', state.commands, raw=answer)
        return SessionSetup(session_id, list(state.options), list(state.commands), named, [])

    async def new_session(self, cwd: str, servers: list[McpServer], *, directories: list[str] | None = None,
                          options: list[OptionValue] | None = None,
                          system_prompt: SystemPrompt | None = None) -> SessionSetup:
        params = self.setup(cwd, servers, directories, options, system_prompt)
        answer = obj(await self.request('session/new', params))
        session_id = answer.get('sessionId')
        if not isinstance(session_id, str) or not session_id:
            raise RequestError(-32603, 'The harness answered session/new without a session id.')
        return await self.given(options or [], self.take(session_id, answer), 'configOptions' in params)

    async def resume_session(self, session_id: str, cwd: str, servers: list[McpServer], *, replay: bool = False,
                             directories: list[str] | None = None, options: list[OptionValue] | None = None,
                             system_prompt: SystemPrompt | None = None) -> SessionSetup:
        params = {'sessionId': session_id, **self.setup(cwd, servers, directories, options, system_prompt)}
        state = self.session(session_id)
        if replay:  # rebuilt from the replay rather than merged into, as ACP says
            params['replayFrom'] = {'type': 'start'}
            state.reset_history()
            state.replaying, state.replay_done = True, False
        try:
            answer = obj(await self.request('session/resume', params))
        finally:
            state.replaying = False
        if replay and not state.replay_done:  # a replay that ended without replay_complete was cut short
            self.tell(session_id, REPLAY, '', {'complete': False})
        return await self.given(options or [], self.take(session_id, answer), 'configOptions' in params)

    async def fork_session(self, session_id: str, cwd: str, servers: list[McpServer]) -> SessionSetup:
        if not self.caps().fork:
            raise Unsupported('session/fork', 2)
        params = {'sessionId': session_id, **self.setup(cwd, servers, None, None, None)}
        answer = obj(await self.request('session/fork', params))
        made = answer.get('sessionId')
        if not isinstance(made, str) or not made:
            raise RequestError(-32603, 'The harness answered session/fork without a session id.')
        return self.take(made, answer)

    async def session_options(self, cwd: str, session_id: str | None = None) -> SessionSetup:
        if not self.caps().options:
            raise Unsupported('session/options', 2)
        answer = obj(await self.request('session/options', {'cwd': cwd, **({'sessionId': session_id}
                                                                          if session_id else {})}))
        options = [option_of(one, 'configId', 'groupId') for one in dicts(answer.get('configOptions'))]
        commands = [command_of(one) for one in dicts(answer.get('availableCommands'))]
        return SessionSetup(session_id or '', options, commands, isinstance(answer.get('configOptions'), list), [])

    async def list_sessions(self, cwd: str | None = None, cursor: str | None = None
                            ) -> tuple[list[dict[str, Any]], str | None]:
        if not self.caps().list:
            raise Unsupported('session/list', 2)
        answer = obj(await self.request('session/list', {**({'cwd': cwd} if cwd else {}),
                                                         **({'cursor': cursor} if cursor else {})}))
        return dicts(answer.get('sessions')), text_or_none(answer.get('nextCursor'))

    async def close_session(self, session_id: str) -> None:
        if not self.caps().close:
            raise Unsupported('session/close', 2)
        await self.request('session/close', {'sessionId': session_id})

    async def delete_session(self, session_id: str) -> None:
        if not self.caps().delete:
            raise Unsupported('session/delete', 2)
        await self.request('session/delete', {'sessionId': session_id})

    # ------------------------------------------------------------------ the prompt turn

    def prompt(self, session_id: str, blocks: list[dict[str, Any]]) -> Prompt:
        made = self.handle_for(session_id)

        async def send() -> None:
            try:
                answer = obj(await self.request('session/prompt', {'sessionId': session_id, 'prompt': blocks}))
            except Exception as error:  # noqa: BLE001  an error answer: the message was not inserted
                self.end_prompt(made, None, error)
                return
            if not made.accepted.done():
                made.accepted.set_result(str(answer.get('messageId') or ''))
        self.spawn(send())
        return made

    async def cancel(self, session_id: str) -> None:
        await self.notify('session/cancel', {'sessionId': session_id})

    async def set_option(self, session_id: str, config_id: str, value: str | bool) -> list[ConfigOption]:
        state = self.session(session_id)
        answer = obj(await self.request('session/set_config_option', {
            'sessionId': session_id, 'configId': config_id, 'type': 'boolean' if isinstance(value, bool) else 'id',
            'value': value}))
        if isinstance(answer.get('configOptions'), list):
            state.options = [option_of(one, 'configId', 'groupId') for one in dicts(answer['configOptions'])]
        else:  # the full list is required; an answer without it has taken the value as given
            for one in state.options:
                if one.config_id == config_id:
                    one.current = value
        self.tell(session_id, OPTIONS, config_id, state.options, raw=answer)
        return list(state.options)

    async def login(self, method_id: str) -> None:
        await self.request('auth/login', {'methodId': method_id})

    async def logout(self) -> None:
        if not self.caps().logout:
            raise Unsupported('auth/logout', 2, 'the harness lists no login methods')
        await self.request('auth/logout', {})

    # ------------------------------------------------------------------ updates

    def apply(self, session_id: str, update: dict[str, Any]) -> None:
        state = self.session(session_id)
        kind = update.get('sessionUpdate')
        if kind in CHUNKS or kind in WHOLE:
            self.message(state, str(kind), update)
        elif kind == 'tool_call_update':
            ident = update.get('toolCallId')
            if not isinstance(ident, str):
                self.tell(session_id, INVALID, str(kind), update, raw=update)
                return
            call = self.tool_call(state, ident, update)
            self.tell(session_id, TOOL_CALL, ident, call, raw=update)
        elif kind == 'tool_call_content_chunk':
            ident, item = update.get('toolCallId'), update.get('content')
            if not isinstance(ident, str) or not isinstance(item, dict):
                self.tell(session_id, INVALID, str(kind), update, raw=update)
                return
            call = state.tool_calls.get(ident) or state.tool_calls.setdefault(ident, ToolCall(ident, {}))
            call.fields['content'] = [*dicts(call.fields.get('content')), cast(dict[str, Any], item)]
            self.tell(session_id, TOOL_CALL, ident, call, item, raw=update)
        elif kind == 'plan_update':
            plan = obj(update.get('plan'))
            ident = plan.get('planId')
            if not isinstance(ident, str):
                self.tell(session_id, INVALID, str(kind), update, raw=update)
                return
            state.plans[ident] = Plan(ident, str(plan.get('type') or 'items'), dicts(plan.get('entries')), plan)
            self.tell(session_id, PLAN, ident, state.plans[ident], raw=update)
        elif kind in ('terminal_update', 'terminal_output_chunk'):
            self.terminal(state, str(kind), update)
        elif kind == 'state_update':
            self.state_update(state, update)
        elif kind == 'replay_complete':
            state.replaying, state.replay_done = False, True
            self.tell(session_id, REPLAY, '', {'complete': True}, raw=update)
        elif kind == 'config_option_update':
            state.options = [option_of(one, 'configId', 'groupId') for one in dicts(update.get('configOptions'))]
            self.tell(session_id, OPTIONS, '', state.options, raw=update)
        elif kind == 'available_commands_update':
            state.commands = [command_of(one) for one in dicts(update.get('availableCommands'))]
            self.tell(session_id, COMMANDS, '', state.commands, raw=update)
        elif kind == 'session_info_update':
            patched(state.info, update, ('sessionUpdate',))
            self.tell(session_id, INFO, '', state.info, raw=update)
        elif kind == 'usage_update':
            patched(state.usage, update, ('sessionUpdate',))
            self.tell(session_id, USAGE, '', state.usage, raw=update)
        elif kind == 'notice':
            self.tell(session_id, NOTICE, '', update, raw=update)
        elif kind in ('compaction_update', 'compaction_summary_chunk'):
            self.tell(session_id, COMPACTION, str(kind), update, raw=update)
        else:  # a kind v2 adds later, or an extension's: kept as received
            self.tell(session_id, OTHER, str(kind), update, raw=update)

    def message(self, state: SessionState, kind: str, update: dict[str, Any]) -> None:
        ident = update.get('messageId')
        role = CHUNKS.get(kind) or WHOLE[kind]
        content = update.get('content')
        chunk = kind in CHUNKS
        if not isinstance(ident, str) or chunk and not isinstance(content, dict) or \
                not chunk and 'content' in update and content is not None and not isinstance(content, list):
            self.tell(state.session_id, INVALID, kind, update, raw=update)
            return
        message = state.messages.get((role, ident))
        if message is None:
            message = state.messages[(role, ident)] = Message(role, ident, [], None)
        if chunk:
            appended(message.content, cast(dict[str, Any], content))
        elif 'content' in update:  # a whole message: null or [] clears it, an array replaces it
            message.content = [dict(block) for block in dicts(content)]
        if '_meta' in update:
            message.meta = meta_patched(message.meta, update['_meta'])
        self.tell(state.session_id, MESSAGE, f'{role}:{ident}', message, content if chunk else None, raw=update)

    def tool_call(self, state: SessionState, ident: str, update: dict[str, Any]) -> ToolCall:
        """The first update of an id makes the call; each later one patches it."""
        call = state.tool_calls.get(ident)
        if call is None:
            call = state.tool_calls[ident] = ToolCall(ident, {})
        patched(call.fields, update, ('sessionUpdate', 'toolCallId'))
        return call

    def terminal(self, state: SessionState, kind: str, update: dict[str, Any]) -> None:
        ident = update.get('terminalId')
        if not isinstance(ident, str):
            self.tell(state.session_id, INVALID, kind, update, raw=update)
            return
        held = state.terminals.get(ident)
        if held is None:
            held = state.terminals[ident] = Terminal(ident, {}, bytearray())
        try:
            if kind == 'terminal_output_chunk':
                data = base64.b64decode(str(update.get('data') or ''), validate=True)
                held.output += data
                self.tell(state.session_id, TERMINAL, ident, held, data, raw=update)
                return
            if 'output' in update:  # a snapshot replaces every byte held; null clears them
                snapshot = update['output']
                held.output = bytearray(base64.b64decode(str(obj(snapshot).get('data') or ''), validate=True)) \
                    if isinstance(snapshot, dict) else bytearray()
        except (binascii.Error, ValueError):
            self.tell(state.session_id, INVALID, kind, update, raw=update)
            return
        patched(held.fields, update, ('sessionUpdate', 'terminalId', 'output'))
        self.tell(state.session_id, TERMINAL, ident, held, raw=update)

    def state_update(self, state: SessionState, update: dict[str, Any]) -> None:
        """The session's foreground work. An idle ends each prompt whose work it ends: one sent while the session was
        idle, once work began after it was sent; one sent while work ran, once it has been accepted (an agent inserts
        it into the running work, or holds it and answers once the work before it is idle)."""
        value = update.get('state')
        if not isinstance(value, str):
            self.tell(state.session_id, INVALID, 'state_update', update, raw=update)
            return
        stop, background = update.get('stopReason'), update.get('background')
        idle = value == IDLE
        turn = state.turn = Turn(  # a snapshot of the whole state, as v2 says each state_update is
            value, stop if idle and isinstance(stop, str) else None,  # a missing or malformed stop reason is none
            obj(update.get('error')) or None if idle else None, obj(update.get('usage')) or None if idle else None,
            list(cast(list[Any], background)) if isinstance(background, list) else None)
        self.tell(state.session_id, TURN, '', turn, raw=update)
        for made in list(self.waiting.get(state.session_id) or []):
            if value in ACTIVE:
                made.active_seen = True
            elif value == IDLE and (made.active_seen and not made.active_at_send or
                                    made.active_at_send and made.accepted.done()):
                self.end_prompt(made, turn)

    # ------------------------------------------------------------------ the agent's requests

    def read_permission(self, params: dict[str, Any], key: Any) -> PermissionRequest:
        session_id = str(params.get('sessionId') or '')
        state = self.session(session_id)
        given = params.get('subject')
        subject = obj(given)
        kind = text_or_none(subject.get('type')) if isinstance(given, dict) else None
        call: ToolCall | None = None
        command: dict[str, Any] | None = None
        if kind == 'tool_call':  # its tool call is an ordinary upsert of the call
            update = obj(subject.get('toolCall'))
            ident = update.get('toolCallId')
            if isinstance(ident, str):
                call = self.tool_call(state, ident, update)
                self.tell(session_id, TOOL_CALL, ident, call, raw=update)
        elif kind == 'command':
            command = subject
        return PermissionRequest(
            session_id=session_id, title=str(params.get('title') or ''),
            description=text_or_none(params.get('description')), subject=kind, tool_call=call, command=command,
            options=[PermissionOption(str(one.get('optionId') or ''), str(one.get('name') or one.get('optionId')),
                                      str(one.get('kind') or '')) for one in dicts(params.get('options'))],
            key=key, raw=params)

    def answer_permission(self, chosen: str | None) -> dict[str, Any]:
        if chosen is None:
            return {'outcome': {'outcome': 'cancelled'}}
        return {'outcome': {'outcome': 'selected', 'optionId': chosen}}
