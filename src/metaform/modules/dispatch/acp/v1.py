"""The ACP v1 adapter: v1's wire shapes, capabilities, validation and lifecycle, behind the model.

v1 is the protocol's stable version (agentclientprotocol.com, protocol/v1). How it reaches the model, which follows
v2:

- the turn: `session/prompt` stays pending for the whole turn, so the adapter reports `running` once the prompt is
  written and `idle` with the stop reason when its answer arrives (an error answer is an idle `error`, as v2 says a
  failure after insertion is). While an agent's request of the turn waits on the person, the turn is
  `requires_action`, which v1 leaves implicit.
- messages: chunks carry no id (it is optional in v1), so the adapter gives each message one, `v1-<role>-<n>`, a
  message running until an update of any other kind. The prompt itself is the user message `v1-user-<n>`, made from
  the request as it is written; a harness that repeats the prompt back as user chunks (claude-agent-acp's
  replay-user-messages) is heard as that same message, not a second one.
- tool calls: `tool_call` is the first update of its id; in v1 a null field is the same as one left out.
- settings: session modes are presented as one config option of category `mode` (unless a config option already is
  the mode, which ACP says supersedes them), set with `session/set_mode`.
- resume: with the history replayed is `session/load`, without is `session/resume`, each where the harness offers it.
- the client's own files and terminals, which v1 has, are not offered: they serve an editor, and Metaform has none.
"""
from __future__ import annotations

from typing import Any, cast

from acp.exceptions import RequestError

from .model import (
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
    REQUIRES_ACTION,
    RUNNING,
    TOOL_CALL,
    TURN,
    USAGE,
    Capabilities,
    Choice,
    Client,
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
    ToolCall,
    Turn,
    Unsupported,
    appended,
    command_of,
    dicts,
    error_of,
    obj,
    option_of,
    patched,
    text_or_none,
)

UNSUPPORTED_VERSION = -32022
CHUNKS = {'user_message_chunk': 'user', 'agent_message_chunk': 'agent', 'agent_thought_chunk': 'thought'}


def text_of(blocks: list[dict[str, Any]]) -> str:
    return ''.join(str(block.get('text') or '') for block in blocks if block.get('type') == 'text')


class V1(Harness):
    protocol = 1

    def __init__(self, process: Any, client: Client) -> None:
        super().__init__(process, client)
        self.writing: dict[str, list[tuple[Prompt, list[dict[str, Any]]]]] = {}  # prompts sent, not yet written

    # ------------------------------------------------------------------ initialize

    async def initialize(self, info: dict[str, str], offer: Offer, timeout: float) -> Capabilities:
        session: dict[str, Any] = {'configOptions': {'boolean': {}}}
        if offer.notices:
            session['notices'] = {}
        if offer.compaction:
            session['compaction'] = {}
        capabilities: dict[str, Any] = {'session': session, 'auth': {'terminal': offer.terminal_login}}
        if offer.elicitation:
            capabilities['elicitation'] = {'form': {}, 'url': {}}
        if offer.subagents:
            capabilities['subagents'] = {}
        try:
            given = await self.request('initialize', {'protocolVersion': 1, 'clientCapabilities': capabilities,
                                                      'clientInfo': info}, timeout)
        except RequestError as error:
            if error.code == UNSUPPORTED_VERSION:  # a harness that knows only v2
                versions = obj(error.data).get('supported')
                listed = cast(list[Any], versions) if isinstance(versions, list) else []
                raise SelectedVersion(2 if 2 in listed else None, f'initialize asking for v1 was refused: {error}') \
                    from error
            raise
        answer = obj(given)
        version = answer.get('protocolVersion')
        if version != 1:
            raise SelectedVersion(version if isinstance(version, int) else None,
                                  f'the harness selected ACP protocol {version!r} when asked for v1')
        self.capabilities = self.read_capabilities(answer, offer)
        return self.capabilities

    def read_capabilities(self, answer: dict[str, Any], offer: Offer) -> Capabilities:
        agent = obj(answer.get('agentCapabilities'))
        session, prompt = obj(agent.get('sessionCapabilities')), obj(agent.get('promptCapabilities'))
        mcp, auth = obj(agent.get('mcpCapabilities')), obj(agent.get('auth'))
        system = session.get('systemPrompt')

        def marked(given: dict[str, Any], key: str) -> bool:
            return isinstance(given.get(key), dict)
        logins = [Login(method_id=str(one.get('id') or ''), name=str(one.get('name') or one.get('id')),
                        type=str(one.get('type') or 'agent'), description=text_or_none(one.get('description')),
                        args=[str(arg) for arg in cast(list[Any], one.get('args') or [])],
                        env={str(key): str(value) for key, value in obj(one.get('env')).items()},
                        vars=dicts(one.get('vars')), link=text_or_none(one.get('link')), raw=one)
                  for one in dicts(answer.get('authMethods'))]
        return Capabilities(
            protocol=1, info=obj(answer.get('agentInfo')), sessions=True, list=marked(session, 'list'),
            resume=marked(session, 'resume'), replay=bool(agent.get('loadSession')), close=marked(session, 'close'),
            delete=marked(session, 'delete'), fork=marked(session, 'fork'), options=marked(session, 'options'),
            system_prompt=isinstance(system, dict),
            system_prompt_override=marked(obj(obj(system).get('mode')), 'override'),
            image=bool(prompt.get('image')), audio=bool(prompt.get('audio')),
            embedded_context=bool(prompt.get('embeddedContext')), mcp_stdio=True, mcp_http=bool(mcp.get('http')),
            additional_directories=marked(session, 'additionalDirectories'), providers=marked(agent, 'providers'),
            steering=bool(obj(obj(answer.get('_meta')).get('steering')).get('supported')),
            auth_status='authStatus' in obj(agent.get('_meta')), logout=marked(auth, 'logout'),
            terminal_login=offer.terminal_login, logins=logins, raw=answer)

    # ------------------------------------------------------------------ sessions

    def setup(self, cwd: str, servers: list[McpServer], directories: list[str] | None,
              options: list[OptionValue] | None, system_prompt: SystemPrompt | None) -> dict[str, Any]:
        caps = self.caps()
        wired: list[dict[str, Any]] = []
        for server in servers:
            if server.url is not None:
                if not caps.mcp_http:
                    raise Unsupported(f'the MCP server {server.name} over http', 1)
                wired.append({'type': 'http', 'name': server.name, 'url': server.url,
                              'headers': [{'name': key, 'value': value} for key, value in server.headers.items()]})
            else:  # v1's stdio server has no type, and its args and env are always sent
                wired.append({'name': server.name, 'command': server.command or '', 'args': list(server.args),
                              'env': [{'name': key, 'value': value} for key, value in server.env.items()]})
        params: dict[str, Any] = {'cwd': cwd, 'mcpServers': wired}
        if directories:
            if not caps.additional_directories:
                raise Unsupported('additional directories', 1)
            params['additionalDirectories'] = list(directories)
        if options and caps.options:  # v1's entries name a type only for a switch
            params['configOptions'] = [{'configId': one.config_id, 'value': one.value,
                                        **({'type': 'boolean'} if isinstance(one.value, bool) else {})}
                                       for one in options]
        if system_prompt is not None:
            if not caps.system_prompt:
                raise Unsupported('a system prompt at session setup', 1)
            if system_prompt.mode == 'override' and not caps.system_prompt_override:
                raise Unsupported('a system prompt that overrides the harness\'s own', 1)
            if system_prompt.mode not in ('append', 'override'):
                raise ValueError(f'A system prompt is appended or overrides, not {system_prompt.mode}.')
            params['systemPrompt'] = {'mode': system_prompt.mode,
                                      'content': [{'type': 'text', 'text': system_prompt.text}]}
        return params

    def shown(self, state: SessionState, options: list[ConfigOption] | None = None) -> None:
        """The session's settings: its config options, and its session modes as one more, of category mode, unless a
        config option already is the mode."""
        given = [one for one in state.options if one.source == 'option'] if options is None else options
        modes = state.v1_modes
        available = dicts((modes or {}).get('availableModes'))
        if available and not any(one.category == 'mode' for one in given):
            taken = {one.config_id for one in given}
            current = (modes or {}).get('currentModeId')
            given = [ConfigOption(config_id='mode' if 'mode' not in taken else 'session_mode', name='Mode',
                                  description=None, category='mode', type='select',
                                  current=current if isinstance(current, str) else None,
                                  choices=[Choice(str(one.get('id')), str(one.get('name') or one.get('id')),
                                                  text_or_none(one.get('description')), None) for one in available],
                                  source='mode', raw=cast(dict[str, Any], modes)), *given]
        state.options = given

    def take(self, session_id: str, answer: dict[str, Any]) -> SessionSetup:
        state = self.session(session_id)
        named = isinstance(answer.get('modes'), dict) or isinstance(answer.get('configOptions'), list)
        if isinstance(answer.get('modes'), dict):
            state.v1_modes = cast(dict[str, Any], answer['modes'])
        if named:
            self.shown(state, [option_of(one, 'id', 'group') for one in dicts(answer.get('configOptions'))]
                       if isinstance(answer.get('configOptions'), list) else None)
            self.tell(session_id, OPTIONS, '', state.options, raw=answer)
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
        caps = self.caps()
        if replay and not caps.replay:
            raise Unsupported('a resume that replays the history', 1, 'the harness offers no session/load')
        if not replay and not caps.resume:
            raise Unsupported('a resume without replay', 1, 'the harness offers no session/resume')
        params = {'sessionId': session_id, **self.setup(cwd, servers, directories, options, system_prompt)}
        state = self.session(session_id)
        if replay:
            state.reset_history()
            state.replaying = True
            state.v1_open = None
        try:
            answer = obj(await self.request('session/load' if replay else 'session/resume', params))
        finally:
            state.replaying = False
            state.v1_open = None
        if replay:  # v1 says the replay is over by answering session/load
            self.tell(session_id, REPLAY, '', {'complete': True})
        return await self.given(options or [], self.take(session_id, answer), 'configOptions' in params)

    async def fork_session(self, session_id: str, cwd: str, servers: list[McpServer]) -> SessionSetup:
        if not self.caps().fork:
            raise Unsupported('session/fork', 1)
        params = {'sessionId': session_id, **self.setup(cwd, servers, None, None, None)}
        answer = obj(await self.request('session/fork', params))
        made = answer.get('sessionId')
        if not isinstance(made, str) or not made:
            raise RequestError(-32603, 'The harness answered session/fork without a session id.')
        return self.take(made, answer)

    async def session_options(self, cwd: str, session_id: str | None = None) -> SessionSetup:
        if not self.caps().options:
            raise Unsupported('session/options', 1)
        answer = obj(await self.request('session/options', {'cwd': cwd, **({'sessionId': session_id}
                                                                          if session_id else {})}))
        probe = SessionState('')
        if isinstance(answer.get('modes'), dict):
            probe.v1_modes = cast(dict[str, Any], answer['modes'])
        self.shown(probe, [option_of(one, 'id', 'group') for one in dicts(answer.get('configOptions'))])
        named = isinstance(answer.get('modes'), dict) or isinstance(answer.get('configOptions'), list)
        return SessionSetup(session_id or '', probe.options, [], named, [])

    async def list_sessions(self, cwd: str | None = None, cursor: str | None = None
                            ) -> tuple[list[dict[str, Any]], str | None]:
        if not self.caps().list:
            raise Unsupported('session/list', 1)
        answer = obj(await self.request('session/list', {**({'cwd': cwd} if cwd else {}),
                                                         **({'cursor': cursor} if cursor else {})}))
        return dicts(answer.get('sessions')), text_or_none(answer.get('nextCursor'))

    async def close_session(self, session_id: str) -> None:
        if not self.caps().close:
            raise Unsupported('session/close', 1)
        await self.request('session/close', {'sessionId': session_id})

    async def delete_session(self, session_id: str) -> None:
        if not self.caps().delete:
            raise Unsupported('session/delete', 1)
        await self.request('session/delete', {'sessionId': session_id})

    # ------------------------------------------------------------------ the prompt turn

    def prompt(self, session_id: str, blocks: list[dict[str, Any]]) -> Prompt:
        made = self.handle_for(session_id)
        self.writing.setdefault(session_id, []).append((made, blocks))

        async def send() -> None:
            try:
                answer = obj(await self.request('session/prompt', {'sessionId': session_id, 'prompt': blocks}))
            except RequestError as error:  # v1 says a failed turn this way: an idle error, as v2 does
                self.finish(made, 'error', error_of(error), None)
            except Exception as error:  # noqa: BLE001  never written, or the harness is gone
                held = self.writing.get(session_id) or []
                if (made, blocks) in held:
                    held.remove((made, blocks))
                self.end_prompt(made, None, error)
            else:
                stop = answer.get('stopReason')
                usage = answer.get('usage')
                self.finish(made, stop if isinstance(stop, str) else None, None,
                            cast(dict[str, Any], usage) if isinstance(usage, dict) else None)
        self.spawn(send())
        return made

    def sent_message(self, method: Any, message: dict[str, Any]) -> None:
        """The prompt is written: it is the session's user message, under an id of the adapter's, and its work
        runs."""
        if method != 'session/prompt':
            return
        session_id = str(obj(message.get('params')).get('sessionId') or '')
        held = self.writing.get(session_id) or []
        if not held:
            return
        made, blocks = held.pop(0)
        state = self.session(session_id)
        state.v1_count += 1
        ident = f'v1-user-{state.v1_count}'
        state.v1_open = None
        state.v1_echo = (ident, text_of(blocks), '')
        state.messages[('user', ident)] = Message('user', ident, [dict(block) for block in blocks], None)
        self.tell(session_id, MESSAGE, f'user:{ident}', state.messages[('user', ident)])
        if not made.accepted.done():
            made.accepted.set_result(ident)
        made.active_seen = True
        state.turn = Turn(RUNNING)
        self.tell(session_id, TURN, '', state.turn)

    def finish(self, made: Prompt, stop: str | None, error: dict[str, Any] | None,
               usage: dict[str, Any] | None) -> None:
        state = self.session(made.session_id)
        state.turn = Turn(IDLE, stop, error, usage, None)
        state.v1_echo, state.v1_open = None, None
        self.tell(made.session_id, TURN, '', state.turn)
        self.end_prompt(made, state.turn)

    async def cancel(self, session_id: str) -> None:
        """Cancel the turn; the agent answers the prompt cancelled. The client answers every permission request and
        question of the session still waiting as cancelled, as v1 asks of it."""
        await self.notify('session/cancel', {'sessionId': session_id})
        for key, (session, _) in list(self.asked.items()):
            if session == session_id:
                self.withdraw(key, cancelled=True)

    def user_wait(self, session_id: str | None, change: int) -> None:
        if session_id is None:
            return
        state = self.session(session_id)
        state.user_waits = max(0, state.user_waits + change)
        moved = REQUIRES_ACTION if state.user_waits and state.turn.state == RUNNING else \
            RUNNING if not state.user_waits and state.turn.state == REQUIRES_ACTION else None
        if moved is not None:
            state.turn = Turn(moved)
            self.tell(session_id, TURN, '', state.turn)

    async def set_option(self, session_id: str, config_id: str, value: str | bool) -> list[ConfigOption]:
        state = self.session(session_id)
        found = state.option(config_id)
        if found is not None and found.source == 'mode':
            if not isinstance(value, str):
                raise ValueError(f'{found.name} is a choice, not on or off.')
            await self.request('session/set_mode', {'sessionId': session_id, 'modeId': value})
            state.v1_modes = {**(state.v1_modes or {}), 'currentModeId': value}
            self.shown(state)
            self.tell(session_id, OPTIONS, config_id, state.options)
            return list(state.options)
        answer = obj(await self.request('session/set_config_option', {
            'sessionId': session_id, 'configId': config_id, 'value': value,
            **({'type': 'boolean'} if isinstance(value, bool) else {})}))
        if isinstance(answer.get('configOptions'), list):
            self.shown(state, [option_of(one, 'id', 'group') for one in dicts(answer['configOptions'])])
        else:  # an agent that answers with nothing has taken the value as given
            for one in state.options:
                if one.config_id == config_id:
                    one.current = value
        self.tell(session_id, OPTIONS, config_id, state.options, raw=answer)
        return list(state.options)

    async def login(self, method_id: str) -> None:
        await self.request('authenticate', {'methodId': method_id})

    async def logout(self) -> None:
        if not self.caps().logout:
            raise Unsupported('logout', 1)
        await self.request('logout', {})

    # ------------------------------------------------------------------ updates

    def apply(self, session_id: str, update: dict[str, Any]) -> None:
        state = self.session(session_id)
        kind = update.get('sessionUpdate')
        if kind in CHUNKS:
            self.chunk(state, str(kind), update)
            return
        state.v1_open = None  # any other update ends the message being written
        if kind in ('tool_call', 'tool_call_update'):
            ident = update.get('toolCallId')
            if not isinstance(ident, str):
                self.tell(session_id, INVALID, str(kind), update, raw=update)
                return
            call = self.tool_call(state, ident, update)
            self.tell(session_id, TOOL_CALL, ident, call, raw=update)
        elif kind == 'plan':  # v1 has one plan, replaced whole
            state.plans['plan'] = Plan('plan', 'items', dicts(update.get('entries')), update)
            self.tell(session_id, PLAN, 'plan', state.plans['plan'], raw=update)
        elif kind == 'available_commands_update':
            state.commands = [command_of(one) for one in dicts(update.get('availableCommands'))]
            self.tell(session_id, COMMANDS, '', state.commands, raw=update)
        elif kind == 'config_option_update':
            self.shown(state, [option_of(one, 'id', 'group') for one in dicts(update.get('configOptions'))])
            self.tell(session_id, OPTIONS, '', state.options, raw=update)
        elif kind == 'current_mode_update':
            state.v1_modes = {**(state.v1_modes or {}), 'currentModeId': update.get('currentModeId')}
            self.shown(state)
            self.tell(session_id, OPTIONS, '', state.options, raw=update)
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
        else:  # a kind the model does not have (a subagent's, an extension's): kept as received
            self.tell(session_id, OTHER, str(kind), update, raw=update)

    def chunk(self, state: SessionState, kind: str, update: dict[str, Any]) -> None:
        role = CHUNKS[kind]
        content = update.get('content')
        if not isinstance(content, dict):
            self.tell(state.session_id, INVALID, kind, update, raw=update)
            return
        block = cast(dict[str, Any], content)
        if role == 'user' and state.v1_echo is not None and state.v1_open is None:
            ident, text, heard = state.v1_echo
            if block.get('type') != 'text':
                return  # a link or an image the prompt carried, repeated
            now = heard + str(block.get('text') or '')
            if text.startswith(now):
                state.v1_echo = (ident, text, now)
                return  # the prompt, repeated: it is the user message already
            state.v1_echo = None  # not the prompt: a message of its own
        given = update.get('messageId')
        if isinstance(given, str) and given:
            ident = given
        elif state.v1_open is not None and state.v1_open[0] == role:
            ident = state.v1_open[1]
        else:
            state.v1_count += 1
            ident = f'v1-{role}-{state.v1_count}'
        state.v1_open = (role, ident)
        message = state.messages.get((role, ident))
        if message is None:
            message = state.messages[(role, ident)] = Message(role, ident, [], None)
        appended(message.content, block)
        self.tell(state.session_id, MESSAGE, f'{role}:{ident}', message, block, raw=update)

    def tool_call(self, state: SessionState, ident: str, update: dict[str, Any]) -> ToolCall:
        """`tool_call` makes the call, `tool_call_update` patches it; a null field in v1 is one left out."""
        call = state.tool_calls.get(ident)
        if call is None:
            call = state.tool_calls[ident] = ToolCall(ident, {})
        patched(call.fields, {key: value for key, value in update.items() if value is not None},
                ('sessionUpdate', 'toolCallId'))
        return call

    # ------------------------------------------------------------------ the agent's requests

    def read_permission(self, params: dict[str, Any], key: Any) -> PermissionRequest:
        session_id = str(params.get('sessionId') or '')
        state = self.session(session_id)
        update = obj(params.get('toolCall'))
        ident = update.get('toolCallId')
        call: ToolCall | None = None
        if isinstance(ident, str):  # the call as the request names it, over what its updates said
            call = self.tool_call(state, ident, update)
            self.tell(session_id, TOOL_CALL, ident, call, raw=update)
        title = str(update.get('title') or update.get('kind') or 'Tool permission')
        return PermissionRequest(
            session_id=session_id, title=title, description=None, subject='tool_call', tool_call=call, command=None,
            options=[PermissionOption(str(one.get('optionId') or ''), str(one.get('name') or one.get('optionId')),
                                      str(one.get('kind') or '')) for one in dicts(params.get('options'))],
            key=key, raw=params)

    def answer_permission(self, chosen: str | None) -> dict[str, Any]:
        if chosen is None:
            return {'outcome': {'outcome': 'cancelled'}}
        return {'outcome': {'outcome': 'selected', 'optionId': chosen}}
