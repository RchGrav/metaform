"""The stdio MCP server: one JSON-RPC message on each line of stdin, one answer on each line of
stdout. In the Rust form the `rmcp` crate does this work; here it is this file.

The answers have the shape of the Rust form's answers, learned from its wire format:

- A request that carries the 2026-07-28 `_meta` fields needs no `initialize`, and its result
  starts with `resultType`.
- A connection whose first accepted request is `initialize` is an older client's. Its requests
  need no `_meta`, and their results have the older shape.
- This form offers the `tools` capability only. It has no change announcements, so it does not
  offer `resources`.
"""
import sys
from typing import Any, BinaryIO

from . import VERSION
from .tool import MapTool, tool_definition
from .values import dumps, loads

PROTOCOL_VERSION = "io.modelcontextprotocol/protocolVersion"
CLIENT_CAPABILITIES = "io.modelcontextprotocol/clientCapabilities"
SERVER_INFO = "io.modelcontextprotocol/serverInfo"

# The protocol versions this server speaks. The last one needs no `initialize`.
SUPPORTED = ["2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25", "2026-07-28"]
STATELESS = "2026-07-28"
# The version an `initialize` gets when it asks for one this server does not speak with a
# handshake.
HANDSHAKE_DEFAULT = "2025-11-25"

INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603
UNSUPPORTED_VERSION = -32022

# Lists that this server holds nothing in. The Rust form answers each with an empty list.
EMPTY_LISTS = {
    "prompts/list": "prompts",
    "resources/list": "resources",
    "resources/templates/list": "resourceTemplates",
}


class Failure(Exception):
    """A JSON-RPC error answer."""

    def __init__(self, code: int, message: str, data: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data


class Server:
    """One connection's MCP session."""

    def __init__(self, tool: MapTool) -> None:
        self.tool = tool
        self.definition = tool_definition()
        self.capabilities: dict[str, Any] = {"tools": {}}
        self.server_info = {"name": "metaform", "version": VERSION}
        # Whether the connection started with `initialize`, as older clients do. It is `None`
        # until the first request is accepted; that request decides it for the connection.
        self.initialized: bool | None = None

    def serve(self, source: BinaryIO, sink: BinaryIO) -> None:
        """Answer each line of `source` until it ends."""
        for raw in source:
            reply = self.answer(raw.decode("utf-8", errors="replace"))
            if reply is not None:
                try:
                    sink.write((dumps(reply) + "\n").encode("utf-8"))
                    sink.flush()
                except BrokenPipeError:
                    # The client closed the connection before it read the answer.
                    return

    def answer(self, line: str) -> dict[str, Any] | None:
        """The answer to one line, or `None` when the line needs none: text that is not JSON, a
        notification, or a client's answer."""
        try:
            message = loads(line)
        except ValueError:
            return None
        invalid = {"jsonrpc": "2.0", "error": {"code": INVALID_REQUEST, "message": "Invalid request"}}
        if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
            return invalid
        if "method" not in message:
            return None if "result" in message or "error" in message else invalid
        method, params = message["method"], message.get("params", {})
        if not isinstance(method, str) or not isinstance(params, dict):
            return invalid
        if "_meta" in params and not isinstance(params["_meta"], dict):
            return invalid
        if "id" not in message:
            return None
        identity = message["id"]
        if isinstance(identity, bool) or not isinstance(identity, (int, str)):
            return invalid
        try:
            return {"jsonrpc": "2.0", "id": identity, "result": self.request(method, params)}
        except Exception as problem:
            # An unexpected error fails only the request that caused it.
            failure = problem if isinstance(problem, Failure) else Failure(INTERNAL_ERROR, str(problem))
            error: dict[str, Any] = {"code": failure.code, "message": failure.message}
            if failure.data is not None:
                error["data"] = failure.data
            return {"jsonrpc": "2.0", "id": identity, "error": error}

    def request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """The result of one request. Raises `Failure` for a JSON-RPC error."""
        if method == "ping" and self.initialized is None:
            # Before the first request is accepted, every ping is answered.
            return {}
        if method == "initialize" and self.is_handshake(params):
            if self.initialized is None:
                self.initialized = True
            asked = params["protocolVersion"]
            return {
                "protocolVersion": asked if asked in SUPPORTED and asked != STATELESS else HANDSHAKE_DEFAULT,
                "capabilities": self.capabilities,
                "serverInfo": self.server_info,
            }
        version = self.version_of(params.get("_meta"), needed=not self.initialized or method == "server/discover")
        if self.initialized is None:
            self.initialized = False
        stateless = version == STATELESS
        if method == "server/discover":
            return {
                "resultType": "complete",
                "supportedVersions": SUPPORTED,
                "capabilities": self.capabilities,
                "ttlMs": 0,
                "cacheScope": "private",
                "_meta": {SERVER_INFO: self.server_info},
            }
        if method == "tools/list":
            return self.listed(stateless, "tools", [self.definition])
        if method in EMPTY_LISTS:
            return self.listed(stateless, EMPTY_LISTS[method], [])
        if method == "tools/call":
            return self.call(stateless, params)
        if method == "ping" and self.initialized and not stateless:
            return {}
        raise Failure(METHOD_NOT_FOUND, method)

    @staticmethod
    def is_handshake(params: dict[str, Any]) -> bool:
        """Whether the parameters of `initialize` have the form an older client sends."""
        info = params.get("clientInfo")
        return (
            isinstance(params.get("protocolVersion"), str)
            and isinstance(params.get("capabilities"), dict)
            and isinstance(info, dict)
            and isinstance(info.get("name"), str)
            and isinstance(info.get("version"), str)
        )

    def version_of(self, meta: Any, needed: bool) -> str | None:
        """The protocol version a request's `_meta` names, or `None` when an initialized
        connection sends a request without the `_meta` fields."""
        fields = meta if isinstance(meta, dict) else {}
        problems = []
        if not isinstance(fields.get(PROTOCOL_VERSION), str):
            problems.append(PROTOCOL_VERSION)
        if not isinstance(fields.get(CLIENT_CAPABILITIES), dict):
            problems.append(CLIENT_CAPABILITIES)
        if problems:
            if not needed:
                return None
            raise Failure(
                INVALID_PARAMS,
                f"request _meta is missing or has malformed required fields: {', '.join(problems)}",
            )
        version = fields[PROTOCOL_VERSION]
        if version not in SUPPORTED:
            raise Failure(
                UNSUPPORTED_VERSION, "Unsupported protocol version", {"requested": version, "supported": SUPPORTED}
            )
        return str(version)

    @staticmethod
    def listed(stateless: bool, name: str, items: list[Any]) -> dict[str, Any]:
        if stateless:
            return {"resultType": "complete", "ttlMs": 0, "cacheScope": "private", name: items}
        return {name: items}

    def call(self, stateless: bool, params: dict[str, Any]) -> dict[str, Any]:
        """`tools/call`: one command of the one tool. An unknown tool is a protocol error
        (JSON-RPC -32602), not a tool result. A refusal is a tool result with `isError` true."""
        name, command = params.get("name"), params.get("arguments")
        if command is None:
            command = {}
        if not isinstance(name, str) or not isinstance(command, dict):
            raise Failure(METHOD_NOT_FOUND, "tools/call")
        if name != self.definition["name"]:
            raise Failure(INVALID_PARAMS, f"unknown tool {name}; the only tool is {self.definition['name']}")
        text, refused = self.tool.call(command)
        result: dict[str, Any] = {"resultType": "complete"} if stateless else {}
        result["content"] = [{"type": "text", "text": text}]
        result["isError"] = refused
        return result


def serve(tool: MapTool) -> None:
    """Serve one connection on this process's stdin and stdout."""
    Server(tool).serve(sys.stdin.buffer, sys.stdout.buffer)
