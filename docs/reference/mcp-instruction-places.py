"""Build mcp-instruction-places.html, beside this file, from the rows below. Print it to PDF with any Chromium:

    chrome --headless --no-pdf-header-footer --print-to-pdf=mcp-instruction-places.pdf mcp-instruction-places.html
"""
import re
from pathlib import Path

A, C, U, N, X = 'always', 'call', 'user', 'never', 'unknown'
LABEL = {A: 'ALWAYS', C: 'ON CALL', U: 'USER', N: 'NEVER', X: 'UNSTATED'}


def t(kind, text=''):
    return f'<span class="tier {kind}">{LABEL[kind]}</span> {text}'


# section: (title, what the primitive is, when it is sent, full: bool, rows)
# full row: (field, what it is, type, limit, triggered by, how the model sees it)
# short row: (field, what it is, type, shown)
SECTIONS = [
    ('Server', 'The program that offers tools, prompts and resources to a host such as Claude Code. Its identity and its '
     'instructions come once, when a client connects.',
     'sent once per connection: <code>server/discover</code> on 2026-07-28, <code>initialize</code> on older revisions', True, [
        ('<code>instructions</code>', 'Plain-language guidance from the server to the model: what the server is for and '
         'when to reach for its tools.', 'string, optional',
         'Claude Code cuts at <b>2,048 chars</b>; <code>CLAUDE_CODE_MAX_MCP_DESCRIPTION_LENGTH</code> changes it',
         'the client connecting', t(A, 'enters once, at session start, and stays in the system prompt. With tool search, it '
                                      'tells the model when to look for your tools.')),
        ('<code>serverInfo</code>: <code>name</code>, <code>version</code>, <code>title</code>, <code>description</code>, '
         '<code>websiteUrl</code>, <code>icons</code>', "The server's identity: what it is called and which version runs.",
         'strings; <code>name</code> and <code>version</code> required', 'none stated', 'the client connecting',
         t(N, 'for display, logging and debugging. Spec: clients SHOULD NOT change behavior on it.')),
    ]),
    ('Tools', 'A tool is a function the model can call. Its definition says what it does and what arguments it takes; '
     "calling it runs the server's code. Tools are the only way a model submits anything to a server.",
     'model-controlled; listed by <code>tools/list</code> at connect and again on <code>list_changed</code>', True, [
        ('<code>name</code>', "The tool's identifier: what the model calls and what permission rules match.",
         'string, required', '1 to 128 chars; <code>A-Z a-z 0-9 _ - .</code>; unique per server', 'connect',
         t(A, 'as <code>mcp__server__name</code>, by name only while tool search defers the rest')),
        ('<code>description</code>', 'What the tool does and how to use it, in prose. The tool\'s only prose field.',
         'string, optional', 'Claude Code cuts at <b>2,048 chars</b>', 'the model finding the tool through ToolSearch',
         t(C, 'part of the loaded tool definition. Put critical details first.')),
        ('<code>inputSchema</code>', 'A JSON Schema listing the arguments the tool accepts: each one\'s name, type, and '
         'whether it is required.', 'JSON Schema object, required; 2020-12 by default', 'none stated', 'same as description',
         t(C, 'the form the model fills in to call. No arguments: <code>{"type":"object","additionalProperties":false}</code>')),
        ('<code>inputSchema.properties.&lt;arg&gt;.description</code>', 'The definition of one argument, written inside '
         'the schema. JSON Schema\'s own keyword, not an MCP field.', 'string', 'none stated by Claude Code',
         'same as description', t(C, 'with <code>enum</code>, <code>default</code> and <code>required</code>, it is how the model learns each field')),
        ('<code>title</code>', 'A label an app can show people instead of the name. Calls always use <code>name</code>.',
         'string, optional; free text', 'none stated', 'connect',
         t(X, 'hosts show <code>title</code>, else <code>annotations.title</code>, else <code>name</code>. Not a place for instruction.')),
        ('<code>annotations.title</code>', 'The older place for the same display name.', 'string, optional', 'none stated',
         'connect', t(X, '<code>title</code> wins when both are set')),
        ('<code>outputSchema</code>', 'A JSON Schema describing the structured data the tool returns.',
         'JSON Schema, optional', 'none stated', 'connect', t(X, 'if present, <code>structuredContent</code> MUST conform')),
        ('<code>annotations.readOnlyHint</code>', 'Says the tool only reads and changes nothing.',
         'bool, default <b>false</b>', 'true / false / omitted', 'connect',
         t(X, 'a hint, untrusted unless the server is trusted')),
        ('<code>annotations.destructiveHint</code>', 'Says the tool may delete or overwrite what exists. False means it '
         'only adds.', 'bool, default <b>true</b>', 'true / false / omitted', 'connect',
         t(X, 'counts only when <code>readOnlyHint</code> is false. No field for a reason.')),
        ('<code>annotations.idempotentHint</code>', 'Says repeating the same call with the same arguments changes '
         'nothing more.', 'bool, default <b>false</b>', 'true / false / omitted', 'connect',
         t(X, 'counts only when not read-only')),
        ('<code>annotations.openWorldHint</code>', "Says the tool reaches outside the server's own domain, like web "
         'search. False: a closed domain, like memory.', 'bool, default <b>true</b>', 'true / false / omitted', 'connect',
         t(X, 'a hint')),
        ('<code>_meta["anthropic/alwaysLoad"]</code>', "Claude Code's key: load this tool's full definition at session "
         'start.', 'bool', 'Claude Code only', 'session start',
         t(A, 'skips the search step. Server-wide: <code>alwaysLoad: true</code> in the config.')),
        ('<code>_meta["anthropic/requiresUserInteraction"]</code>', "Claude Code's key: a person must approve every call.",
         'bool, must be <code>true</code>', 'Claude Code 2.1.199+', 'every call',
         t(U, 'a permission prompt on every call, in every mode; no "don\'t ask again"')),
        ('<code>_meta["anthropic/maxResultSizeChars"]</code>', "Claude Code's key: how large this tool's result may be "
         'before it is saved to a file.', 'integer', 'up to <b>500,000 chars</b>', 'every call', t(N)),
    ]),
    ('Tool results', 'What the server sends back when the model calls a tool. It enters the conversation as the tool '
     'result.', 'the model calling a tool', True, [
        ('<code>content[]</code> text', 'Plain text returned by the call.', '<code>{type:"text", text}</code>',
         'warning at <b>10,000 tokens</b>; cap <b>25,000 tokens</b>, <code>MAX_MCP_OUTPUT_TOKENS</code>', "the model's call",
         t(C, "as the tool result. Over the cap it is saved under the session's <code>tool-results</code> folder and replaced by a file reference.")),
        ('<code>content[]</code> image, audio', 'Media returned by the call.',
         '<code>data</code> base64 string and <code>mimeType</code>, both required', 'always under the token cap',
         "the model's call", t(C, 'images reach the model; images never get the file fallback')),
        ('<code>content[]</code> resource link', 'A pointer to a resource by its URI, without its content.',
         '<code>{type:"resource_link", uri, name}</code>; <code>title</code>, <code>description</code>, <code>mimeType</code>, <code>size</code>',
         'none stated', "the model's call", t(C, 'the pointer only. Need not appear in <code>resources/list</code>.')),
        ('<code>content[]</code> embedded resource', "A resource's content included in the result.",
         '<code>{type:"resource", resource:{uri, text | blob, mimeType}}</code>', 'same cap as text', "the model's call",
         t(C, 'the content, inline')),
        ('<code>structuredContent</code>', 'The result as JSON data, for code to read, matching <code>outputSchema</code>.',
         'any JSON value', 'none stated', "the model's call", t(X, 'spec: also send it as a text block')),
        ('<code>isError</code>', 'Marks the result as a failure the model can correct and retry.', 'bool', 'none',
         "the model's call", t(C, 'spec: clients SHOULD show it to the model')),
        ('<code>annotations.audience</code>', 'Says whom a block is for: the person, the model, or both.',
         'list of <code>"user"</code>, <code>"assistant"</code>', 'on any content block, resource or prompt message',
         'the result', t(X)),
        ('<code>annotations.priority</code>, <code>lastModified</code>', 'How important a block is, and when it last changed.',
         'number 0.0 to 1.0; ISO 8601 string', 'range enforced', 'the result',
         t(X, '1 means effectively required, 0 entirely optional')),
        ('<code>resultType: "input_required"</code>, <code>inputRequests</code>, <code>requestState</code>',
         "An interim result that asks the client for more input, such as a person's answer, before the call can finish.",
         'requests keyed by name; state string', 'none stated', 'the server needing input mid-call',
         t(U, 'carries elicitation; the client answers and retries the call')),
    ]),
    ('Prompts', 'A prompt is a message template the server offers for a person to run, as a slash command in Claude '
     'Code. The model cannot run one.', 'user-controlled; <code>prompts/list</code>, then <code>prompts/get</code>', False, [
        ('<code>name</code>', "The prompt's identifier; it becomes the command name.", 'string, required',
         t(U, 'in the <code>/</code> menu as <code>/server:name (MCP)</code>; <code>/mcp__server__name</code> also runs it')),
        ('<code>title</code>, <code>description</code>', 'Display name and explanation shown in the menu.',
         'strings, optional', t(U, 'menu text')),
        ('<code>arguments[]</code>', 'Values the person types after the command.',
         '<code>{name, title, description, required: bool}</code>', t(U, 'space-separated, one token each')),
        ('<code>messages[].content.text</code>', "<b>The prompt's text.</b> The whole prewritten prompt goes here, "
         "with the person's arguments filled in.", 'string inside <code>{role: "user", content: {type: "text", text}}</code>; '
         'no stated limit', t(C, 'injected into the conversation as the person\'s own message when they run it')),
        ('<code>messages[]</code>', 'The list of messages the prompt returns; one is enough. Content may also be image, '
         'audio, resource link or embedded resource.', '<code>{role: "user" | "assistant", content}</code>',
         t(C, 'each one enters the conversation in order')),
    ]),
    ('Resources', 'A resource is content the server exposes by URI, like a file or a record, to be read. Nothing writes '
     'a resource through MCP.', 'application-driven; <code>resources/list</code>, <code>resources/read</code>', False, [
        ('<code>uri</code>, <code>name</code>', "The resource's address and its name.",
         'strings, required; custom schemes allowed, RFC 3986', t(U, '<code>@server:scheme://path</code> autocomplete')),
        ('<code>title</code>, <code>description</code>, <code>mimeType</code>, <code>size</code>',
         'Display name, explanation, content type and size in bytes.', 'strings; integer bytes',
         t(C, 'through the list tool Claude Code adds')),
        ('contents', 'The content itself.', '<code>{uri, mimeType, text}</code> or <code>{..., blob}</code> base64',
         t(U, 'an @-mention attaches it;') + ' ' + t(C, 'the model reads it with the read tool')),
        ('<code>uriTemplate</code>', 'A URI pattern with variables, for a family of resources.', 'RFC 6570 string', t(X)),
        ('<code>annotations</code>', 'Whom it is for, how important it is, when it changed.',
         'audience, priority, lastModified', t(X)),
    ]),
    ('Elicitation', 'The server asking the person for information in the middle of a request. The answer goes to the '
     'server, never to the model.', 'server asks the person mid-request', False, [
        ('<code>message</code>', 'Why the server is asking.', 'string, required', t(U, 'in a dialog')),
        ('<code>requestedSchema</code>', 'The form fields the person fills in.',
         'JSON Schema; <b>flat object, primitive properties only</b>: string, number, boolean, enum',
         t(U, "form fields, with each property's description")),
        ('<code>url</code>', 'A web page the person opens to complete the request.', 'string, URL mode',
         t(U, 'opens a browser flow')),
        ('result', "The person's answer.", '<code>action: accept | decline | cancel</code>, <code>content</code> dict',
         t(N, 'goes to the server')),
    ]),
    ('Other channels', 'Server messages that reach the person or the host, never the model.', '', False, [
        ('completion <code>values</code>', 'Suggested values while a person types an argument.',
         'list of strings, <b>max 100</b>', t(U, 'suggestions for prompt and template arguments')),
        ('progress <code>message</code>', 'The status of a long-running call.',
         'string, optional; <code>progress</code>, <code>total</code> numbers', t(U, 'in <code>/tasks</code>')),
        ('logging <code>data</code>', 'Log entries from the server. <b>Deprecated.</b>', 'any; <code>level</code> enum', t(N)),
        ('sampling <code>systemPrompt</code>, <code>messages</code>', "The server asking the host's model to generate "
         'text for it. <b>Deprecated.</b>', 'string; list; <code>maxTokens</code> int required',
         t(N, 'a separate generation, not the conversation')),
    ]),
    ('Skills extension', 'A skill is a packaged workflow: a <code>SKILL.md</code> of instructions plus supporting files, '
     'offered through resources.', '<code>io.modelcontextprotocol/skills</code>, Final 2026-09-13; Claude Code is not '
     'on the official client matrix', False, [
        ('<code>skills/list</code> entry', "One skill's address, its frontmatter and its file list.",
         '<code>{uri, frontmatter, resources}</code>; frontmatter holds <code>name</code>, <code>description</code>; '
         '512 files or 16 MiB per skill', 'host decides. The model or the person selects by name and description; '
         '<code>SKILL.md</code> is read only when needed.'),
    ]),
]

PLACES = [
    ('server', '<code>instructions</code>', '2,048 chars', 'once, at session start; stays in the system prompt',
     'only what must precede every tool choice; it is paid for in every session'),
    ('tool', '<code>description</code>', '2,048 chars', 'once, when the tool loads', 'how and when to use this tool; seen before its first call'),
    ('argument', '<code>inputSchema</code> property <code>description</code>', 'none stated', 'once, with its tool',
     'the definition of one field'),
    ('call', 'result <code>text</code>', '25,000 tokens', 'once per call; a second call appends it again',
     'what is needed only at that moment; it cannot govern the call that returned it'),
    ('person', 'prompt <code>messages[].content.text</code>; @-mentioned resource', 'none stated',
     'when the person runs <code>/server:prompt</code> or types <code>@</code>', 'entry points a person chooses; a model cannot run a prompt'),
    ('display', '<code>title</code> on tools, prompts, arguments, resources, <code>serverInfo</code>', 'none stated',
     'shown to people; not stated for the model', 'names for people to read, never instruction'),
]

FACTS = [
    'Three tiers in Claude Code: <b>always</b> holds server instructions and tool names; <b>on call</b> holds tool '
    'definitions, tool results and resources the model reads; <b>user</b> holds prompts, @-mentions and elicitation.',
    'A blind agent, one started by another agent, reaches only <b>instructions</b>, <b>tool definitions</b>, '
    '<b>tool results</b> and <b>resources</b>. It cannot run a prompt.',
    'Submissions only travel through tool arguments. Resources are read-only; prompt arguments and elicitation '
    'answers come from the person.',
    'An instruction must be in context before the call it governs: in <code>instructions</code>, the tool\'s fields, '
    'or an earlier result. Never in the result of that call.',
    'Tool search is on by default: only tool names and server instructions load at session start. '
    '<code>ENABLE_TOOL_SEARCH=false</code> loads every definition up front.',
    'Each tool description and each server\'s instructions are cut at 2,048 characters. Put what matters first.',
    'Annotations describe a whole tool. A tool that mixes read-only, additive and destructive commands cannot set one '
    'true hint.',
    'Stdio servers connect on the older protocol, with <code>initialize</code>, unless '
    '<code>MCP_PROTOCOL_NEGOTIATION=auto</code> is set.',
    'Deprecated in 2026-07-28: Roots, Sampling, Logging.',
    'The spec has no length limits of its own on these strings. Every character limit on this sheet is Claude Code\'s '
    'or the SDK\'s.',
]

CSS = '''
  @page { size: letter landscape; margin: 0.4in 0.45in; }
  :root { --ink:#1b1f24; --muted:#5b6470; --line:#d5dae0; --head:#eef1f4; --band:#f7f8fa;
          --always:#0b6e4f; --call:#1f5fbf; --user:#8a4b00; --never:#6b6f76; --unknown:#9a2f2f; }
  * { box-sizing: border-box; }
  body { margin:0; font:7.6pt/1.25 "Helvetica Neue", Arial, sans-serif; color:var(--ink); background:#fff; }
  h1 { font-size:15pt; margin:0 0 2px; }
  .sub { color:var(--muted); font-size:8pt; margin-bottom:4px; }
  .src { color:var(--muted); font-size:7pt; margin:0 0 7px; }
  .legend { display:flex; gap:14px; flex-wrap:wrap; margin:0 0 8px; font-size:7.6pt; }
  .tier { display:inline-block; font-weight:700; font-size:6.4pt; letter-spacing:.4px; color:#fff; border-radius:3px;
          padding:1px 4px; white-space:nowrap; vertical-align:1px; }
  .always{background:var(--always)} .call{background:var(--call)} .user{background:var(--user)}
  .never{background:var(--never)} .unknown{background:var(--unknown)}
  section { margin-bottom:9px; }
  section.keep { break-inside:avoid; }
  h2 { font-size:9.4pt; margin:0; padding:3px 6px; background:var(--ink); color:#fff; border-radius:3px 3px 0 0;
       display:flex; justify-content:space-between; gap:10px; break-after:avoid; }
  h2 span { font-weight:400; color:#cfd6de; font-size:7.6pt; text-align:right; }
  .def { margin:0; padding:3px 6px; background:#e7ecf2; border:1px solid var(--line); border-bottom:0; font-size:7.8pt;
         break-after:avoid; }
  table { width:100%; border-collapse:collapse; table-layout:fixed; }
  tr { break-inside:avoid; }
  th, td { border:1px solid var(--line); padding:2px 5px; vertical-align:top; text-align:left; }
  th { background:var(--head); font-size:7.2pt; color:var(--muted); font-weight:700; }
  tr:nth-child(even) td { background:var(--band); }
  code { font-family:"SF Mono", Menlo, Consolas, monospace; font-size:7.1pt; }
  td code { overflow-wrap:break-word; }
  td:first-child code { font-weight:700; }
  .facts { columns:2; column-gap:18px; font-size:7.6pt; margin:4px 0 0; padding-left:14px; }
  .facts li { margin-bottom:2px; break-inside:avoid; }
'''


def breakable(field):
    """A field name may break after a dot or a slash, never inside a word."""
    return re.sub(r'(\.|(?<!<)/)(?=[A-Za-z_"&])', r'\1<wbr>', field)


def table(full, rows):
    if full:
        head = ('<tr><th style="width:15%">Field</th><th style="width:22%">What it is</th><th style="width:13%">Type</th>'
                '<th style="width:12%">Limit</th><th style="width:11%">Triggered by</th><th>How the model sees it</th></tr>')
    else:
        head = ('<tr><th style="width:15%">Field</th><th style="width:27%">What it is</th><th style="width:25%">Type</th>'
                '<th>Shown</th></tr>')
    body = ''.join('<tr>' + ''.join(f'<td>{breakable(cell) if i == 0 else cell}</td>' for i, cell in enumerate(row))
                   + '</tr>' for row in rows)
    return f'<table>{head}{body}</table>'


parts = []
for title, what, when, full, rows in SECTIONS:
    span = f' <span>{when}</span>' if when else ''
    keep = ' class="keep"' if len(rows) <= 6 else ''
    parts.append(f'<section{keep}><h2>{title}{span}</h2><p class="def">{what}</p>{table(full, rows)}</section>')
places = ('<section><h2>Where written instruction can go <span>prose only travels in string fields; every hint and '
          'flag goes on its own field</span></h2><table><tr><th style="width:9%">Level</th><th style="width:22%">Field</th>'
          '<th style="width:11%">Limit in Claude Code</th><th style="width:24%">Enters the context</th><th>Use it for</th></tr>'
          + ''.join('<tr>' + ''.join(f'<td>{c}</td>' for c in row) + '</tr>' for row in PLACES) + '</table></section>')
facts = ('<section><h2>Facts that decide the design</h2><ul class="facts">' + ''.join(f'<li>{f}</li>' for f in FACTS)
         + '</ul></section>')

html = f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>MCP Instruction Places</title>
<style>{CSS}</style>
</head>
<body>
<h1>MCP instruction places</h1>
<div class="sub">Every field a server can use to put words in front of a model or a person: what it is, its type, its limit, what triggers it and how the model sees it. Protocol revision <b>2026-07-28</b>, host <b>Claude Code</b>. Checked 2026-10-01 against the spec, the <code>mcp</code> 2.2.0 SDK types and the Claude Code MCP docs.</div>
<div class="src">Sources: modelcontextprotocol.io/specification/2026-07-28, the changelog, discover, tools, prompts, resources, elicitation and completion pages; extensions/skills/overview and extensions/client-matrix; the <code>mcp</code> 2.2.0 Python SDK <code>mcp.types</code>; code.claude.com/docs/en/mcp. UNSTATED marks what the Claude Code docs leave open; test before relying on it.</div>
<div class="legend">
  <div>{t(A, "enters at session start and stays in the model's context")}</div>
  <div>{t(C, 'reaches the model when it acts: finds a tool, calls it, reads a resource')}</div>
  <div>{t(U, 'only a person triggers it')}</div>
  <div>{t(N, 'not shown to the model')}</div>
  <div>{t(X, 'Claude Code docs do not say')}</div>
</div>
{''.join(parts)}
{places}
{facts}
</body>
</html>
'''
Path(__file__).with_name('mcp-instruction-places.html').write_text(html, encoding='utf-8')
print('written')
