"""Dispatch's ACP client: the one place Metaform speaks the Agent Client Protocol.

`model` is what the rest of dispatch and every other module deal with, following ACP v2; `connection` starts a
harness and agrees a version with it; `v1` and `v2` are the two adapters, each owning its version's wire. The
protocol's guidance for supporting both versions is followed as written (agentclientprotocol.com,
protocol/v2/migration, "Supporting v1 and v2 side by side"): two thin protocol layers behind shared application
logic, adapters rather than conversions, and the same tests run against both.
"""
from .connection import START_LIMIT, Starter, connect, starter
from .model import (
    ACTIVE,
    IDLE,
    REQUIRES_ACTION,
    RUNNING,
    BaseClient,
    Capabilities,
    Client,
    ClientTools,
    ConfigOption,
    Elicitation,
    ElicitationAnswer,
    Event,
    Harness,
    Login,
    McpServer,
    Message,
    Offer,
    OptionValue,
    PermissionRequest,
    Prompt,
    SelectedVersion,
    SessionSetup,
    SessionState,
    SystemPrompt,
    ToolCall,
    Turn,
    Unsupported,
)

__all__ = [
    'ACTIVE', 'IDLE', 'REQUIRES_ACTION', 'RUNNING', 'START_LIMIT', 'BaseClient', 'Capabilities', 'Client',
    'ClientTools', 'ConfigOption', 'Elicitation', 'ElicitationAnswer', 'Event', 'Harness', 'Login', 'McpServer',
    'Message', 'Offer', 'OptionValue', 'PermissionRequest', 'Prompt', 'SelectedVersion', 'SessionSetup',
    'SessionState', 'Starter', 'SystemPrompt', 'ToolCall', 'Turn', 'Unsupported', 'connect', 'starter',
]
