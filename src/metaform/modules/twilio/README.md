# twilio

Talk with your system agent, your mascot, by phone, and be called or texted when something needs you, through your own Twilio number.

The module is named for the service it reaches, as every module for an external service is: `metaform twilio ...`, its settings `twilio_*`, its run folder `<home>/run/twilio`. It was built as `phone`, and nothing of that name was released, so nothing is migrated: the PIN is now `METAFORM_TWILIO_PIN` (it was `METAFORM_PHONE_PIN`), and `twilio_number` was `phone_twilio_number`. The paths Twilio calls, `/phone/voice`, `/phone/pin`, `/phone/sms`, `/phone/stream` and `/phone/health`, keep their name: they say what is served there, the phone's webhooks and audio, whatever carries them.

## Purpose

The twilio module answers your Twilio number with your system agent speaking, so you can talk a project over away from the screen, and it calls or texts you when an agent waits on you, looks stuck, reaches its budget or the intake finishes, as you choose. Only your own numbers are answered, called or texted. Your Twilio credentials stay in the environment of the process that runs the bridge; Metaform never stores them or shows them to the page.

## Template version

The template changelog version this module started from: 0.3.0.

## Declaration

`SUPPORTED_OS = ('linux', 'macos', 'windows')`. `DEPENDENCIES = ('starlette>=0.40', 'uvicorn>=0.35', 'websockets>=13', 'httpx>=0.28,<1')`: the bridge is a small ASGI app, since the web GUI's standard-library server has no websockets and Twilio's Media Streams need one; Starlette and uvicorn come with the MCP SDK already, `websockets` is uvicorn's websocket protocol (the bridge uses uvicorn's `websockets-sansio`, which uvicorn has from 0.35), and `httpx` is the simulated call's HTTP client. `SHIPS_DISABLED = False`: the module only shows its status until you turn on `twilio_enabled`. `REMOTE_AGENT = False`.

### Toolbar items and panes

None. The settings screen shows the phone's settings, and `metaform twilio status` says what is missing.

## Common base used

`metaform.module` for the declaration, `Context`, `Stop`, `surface` and `context` (to run dispatch's verbs), and `child_environment`; `metaform.settings` for its settings and to read `web_mascot`; `metaform.prompt_files` for the lines in `resources/prompts.xml`; `metaform.home` for its run folder; `metaform.data.Store` to name a ticket's task in a call and to see the intake finish. `ctx.listen` hears the signals dispatch raises in its runners' processes.

## Prompts

`resources/prompts.xml` holds the standard elements and the phone's own:

- `instructions`: how an agent answers a message that says it comes by phone or by text.
- `on_call`, `on_callback`, `on_text`: sent to the system agent ahead of the first words of a call you made, of a call Metaform placed (with what it was about), and of each text you send. They are in the chat thread with your words.
- `greeting`, `calling`, `texting`: what the phone says when you call, when it calls you, and the text it sends; `<mascot/>` is your mascot's name and `<why/>` what needs you.
- `refusal`, `busy`, `trouble`: said to a caller who is not you, when a call is already in progress, and when the agent or the voice cannot answer.

## Verbs

- `metaform twilio status` (`twilio_status`, read): set up or not and why, each problem with its next step; the webhook URLs to paste into Twilio; whether `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_API_KEY`, `TWILIO_API_SECRET` and `ELEVENLABS_API_KEY` are in the environment, by name only; the numbers masked; whether the bridge runs.
- `metaform twilio serve` (command line, write, open world): runs the bridge on `twilio_bind` (`127.0.0.1` by default), port 7441, the port a Node routes `/phone/*` to, with TLS from `twilio_certificate` when that is set, until stopped by Ctrl-C or SIGTERM (systemd, `docker stop`). It refuses to start while the phone is off, while `twilio_public_url` is not https, without the auth token, an owner number, a Twilio number, the voice module or a project, and when `twilio_caller_proof` is `pin` without a PIN.
- `metaform twilio call [to=<owner number>] [reason...]` (command line, write, open world): rings your phone now through the running bridge; your system agent opens with the reason.
- `metaform twilio text [to=<owner number>] <text...>` (command line, write, open world): texts your phone now.
- `metaform twilio test` (command line, read, task): a whole call simulated on this machine, with a scripted agent and voice and a recorder in place of Twilio's API: no network, no credential. It checks the refusals, the PIN asked of an unattested caller ID, a replayed webhook refused, the stream token, the greeting, the answer and barge-in, and reports the time from the end of your speech to the first audio back, `latency_ms`, as the voice's endpointing pause plus the bridge's own time.
- `metaform twilio check [fix=true]` (`twilio_check`, write, open world): reads where Twilio sends your number's calls and texts, its voice and SMS addresses, from Twilio's API with a GET that changes nothing, and compares them with the address the bridge serves (the running bridge's own, else `twilio_public_url`); it asks `<address>/phone/health` whether the bridge answers there, and asks the number's own address when that is another. Each thing wrong is said with the one step that fixes it, the symptom first: an address that does not answer (so every call hears Twilio's "application error"), an address that is not the bridge's, the bridge not running, no `twilio_public_url`, a TwiML App in the way. A temporary quick tunnel, a `trycloudflare.com`, `loca.lt` or `lhr.life` address, is flagged as temporary wherever it is found. `fix=true`, your own step, never an agent's, sets the number's voice and SMS addresses to `<address>/phone/voice` and `<address>/phone/sms`, by HTTP POST, and takes off a TwiML App in their way; it refuses, changing nothing, when there is no address or the bridge does not answer there, and says so again when the address is a temporary tunnel. On a direct route (below), when `twilio_public_url` resolves to this machine, its interfaces or the public address `https://checkip.amazonaws.com` says it has, the check connects there itself and says which of three things keeps Twilio out: a closed port, a port that does not speak TLS, or a certificate Twilio would refuse, each with its one next step; under WSL2 with NAT networking it also says that a forwarded port reaches Windows and not the bridge. From inside your own network a router without NAT loopback can make an open port look closed, so test from outside before you change anything. The report is kept in `<home>/run/twilio/check.json` and each line of it goes to the log, and nowhere else: nothing is printed and the page shows nothing. `fix=true` is refused over MCP: the person runs it.

`twilio_status` and `twilio_check` are MCP tools only where they help: once the phone is set up (a number, Twilio's credentials or a public address), and only for the person's own AI tool and their system agent, never a worker (ticket bd730760, 2026-10-15; they were command line only since 2026-10-12, to keep them out of every agent's context). Calls, texts and the bridge are the person's own: they are on the command line only, never MCP tools, and `call`, `text` and `serve` refuse to run in an agent's session (one whose runner set `METAFORM_SESSION`, `METAFORM_ROLE` or `METAFORM_WORK`). That refusal guards against an agent's mistakes; it is not a boundary. An agent with a shell runs as your account, so it can clear its environment, run `metaform set` on the phone's settings (`person_only` is enforced over MCP, not on the command line), or read the run file's control token. If you give agents a shell, the phone is only as safe as that shell; see the security model.

## Settings

All global. The ones that decide who reaches your agent, who is called and what it costs are person-only.

| Setting | Default | What it is |
|---|---|---|
| `twilio_enabled` | off | The phone answers, calls and texts at all. On, `metaform web start` starts the bridge too. |
| `twilio_number` | empty | Your Twilio number, E.164. |
| `twilio_owner_numbers` | empty | Your own numbers, E.164: the only callers answered, the only numbers called or texted. Metaform calls the first. |
| `twilio_public_url` | empty | The https address Twilio reaches: your Node, your relay name, or your own tunnel. No path. |
| `twilio_caller_proof` | attested-or-pin | What a call or text from your number must show beyond its caller ID, which can be faked: `attested-or-pin`, `pin`, `attested`, or `caller-id`. See the security model. |
| `twilio_call_when` | none | What calls you: `waiting-for-you`, `stuck`, `budget`, `intake-finished`, or a dispatch signal name. |
| `twilio_text_when` | none | What texts you, from the same list. |
| `twilio_call_gap_minutes` | 15 | The least time between calls Metaform places on its own. |
| `twilio_voice` | empty | An ElevenLabs voice id, or a voice's name on your account, for the phone; `metaform elevenlabs voices` lists them. Empty speaks with the voice `elevenlabs_voices` gives your mascot character. |
| `twilio_hearing` | server | Who hears you: `server` (Whisper on this machine) or `elevenlabs` (Scribe, which receives the audio). |
| `twilio_project` | empty | Whose system agent answers; empty is the project of the folder the bridge runs in. |
| `twilio_bind` | 127.0.0.1 | The address the bridge listens on. Leave it behind a Node or tunnel; set this machine's address, or `0.0.0.0`, for a direct route. |
| `twilio_certificate` | empty | A PEM file with the certificate chain and its key, for the bridge to serve https itself on a direct route. Empty behind your own TLS terminator. |

The language you speak on the phone is the voice module's `voice_language`, the one language Metaform hears you in. The bridge's port is fixed at 7441, where a Node routes `/phone/*` (settings cleanup, 2026-10-15).

## Events

Subscribes to `web.started`, which the web module publishes when `metaform web start` has the page running: with the phone off, nothing happens; with it on and set up, the bridge starts beside it, detached, and checks the number once it listens; with it on but not ready to serve, the check runs there and then once the person has begun setting it up. `web start` prints nothing of either. While it runs, the bridge hears `map.changed` from other processes with `ctx.listen`; a payload carrying a raised dispatch `signal` of its project may place a call or send a text, and a change after which the project has an intake it lacked is `intake-finished`. It publishes `signal.raised` with dispatch's `setup-not-working` when a check nobody asked for (at start, or once the bridge listens) finds a problem with the phone the person has turned on and begun setting up: the feature, what was set up, how to look, and the report. The person's system agent takes it as its next turn and brings it up with them, as a colleague would, with no error text; while none runs, the page shows one closable notice that starts it. Each set of findings is raised once, kept in `<home>/run/twilio/raised.json` as their fingerprint, when, and whether anyone has asked for the check since: it is raised again when the findings change, or a day later when nobody took it up and it still stands. A check someone asks for marks it taken and raises nothing; findings that are gone clear the signal.

Its status hook gives the last check's first problem to `metaform status`, from `check.json`, with no call to Twilio, and no notice to the page.

## Sync and async

`test` is a coroutine. `serve` runs its own event loop with uvicorn. The bridge is asyncio throughout; the voice module's functions, which block, run in threads: transcription in one thread per call fed by a queue, speech a chunk at a time.

## Layers

None, and no tables. The bridge keeps nothing about a call but its log lines.

## Lifecycle and cleanup

`serve` writes `<home>/run/twilio/twilio.json` (its pid, port, the address it is bound to and whether it serves TLS, project, the public address it serves and a one-time control token, readable by your account only) and removes it when it stops, by Ctrl-C or SIGTERM; `<home>/run/twilio/seen.txt` (readable by your account only) keeps the CallSids and MessageSids it acted on, the latest 100,000, so a webhook sent again is refused after a restart too; its log is `<home>/run/twilio/twilio.log`: when calls start and end, refusals, barge-ins and failures, never what was said and never a credential. A call that ends, by hang-up, `stop` or an error, stops its transcription and its speech and leaves the system agent running, its whole answer in the chat.

## Modules relied on

- `dispatch`, through its verbs `system` (start, resume or reuse your system agent), `message` (your words, as your own message) and `sessions` (its answer as it grows, and when its turn ends; each poll passes `since`, the thread's last line before your words, so it reads only the lines after them), and the signals its runners raise.
- `voice`, through what it provides as `voice` (`metaform.module.provided(folder, 'voice')`), only while it is enabled: `speak(folder, text, format='ulaw_8000', character=..., voice=twilio_voice)` streams the voice_tts engine's 8 kHz mu-law audio, in `twilio_voice` when it is set (`voice` is passed only then), and `transcribe_stream(folder, chunks, 'ulaw_8000', language=..., engine=twilio_hearing)` cuts the caller's audio into utterances at pauses and hears them. Speech is not duplicated here.
- `web`, for `web.started` and the mascot's name (`web_mascot`).

## Systems supported

Linux, macOS and Windows.

## Resources owned

The bridge's process while `serve` runs, its port 7441 on `twilio_bind`, its run file and log, one transcription thread per call in progress, and the tasks replying to your texts.

## Installed and direct wheel

The same in both: the bridge needs `starlette`, `uvicorn` and `websockets`, which an installed Metaform carries. Hearing on the server needs the voice extra; speaking needs `ELEVENLABS_API_KEY`.

## Demonstration

```bash
metaform twilio test                      # a simulated call: no Twilio, no engine, no agent
metaform set --twilio-number +15551234567 --twilio-owner-numbers +15557654321
metaform set --twilio-public-url https://alice.metaform.ing --twilio-call-when waiting-for-you --twilio-enabled
metaform twilio status                    # what is missing, and the URLs for Twilio
metaform twilio check                     # where Twilio sends the number's calls, and whether the bridge answers there
metaform twilio check fix=true            # point the number at the bridge, only when it answers
export TWILIO_ACCOUNT_SID=AC... TWILIO_AUTH_TOKEN=... ELEVENLABS_API_KEY=...
metaform twilio serve                     # or metaform web start, with the phone on
metaform twilio call the parser fix is ready for review
```

## Setting it up in Twilio

1. Sign in to the Twilio Console and buy a phone number with Voice and SMS (Phone Numbers > Manage > Buy a number). Set it as `twilio_number`.
2. Put your account's SID and auth token (Console home, Account Info) in the environment of the process that runs the bridge: `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`. Put a PIN of 4 to 12 digits there too, `METAFORM_TWILIO_PIN`: a call whose caller ID is not fully attested is asked for it, and your texts start with it (see the security model). The auth token is what Twilio signs every webhook with, so the bridge needs it to check them. For the calls and texts Metaform places you may add an API key (Account > API keys & tokens > Create API key, Standard), `TWILIO_API_KEY` and `TWILIO_API_SECRET`, so the auth token itself is never sent anywhere.
3. Make the bridge reachable over https and set `twilio_public_url` to that address, with no path:
   - On a Metaform Node (or a relay name, which carries the Node's own TLS), the Node's Caddy routes `/phone/*` to `127.0.0.1:7441` once `metaform node init` has written its Caddyfile again; run `metaform twilio serve` beside the Node's processes, in its network namespace (for example a compose service like `web`, with the command `twilio serve`).
   - On your own machine, point a tunnel of your own (Cloudflare Tunnel, ngrok, Tailscale Funnel) at `http://127.0.0.1:7441`; its https address is `twilio_public_url`.
4. Run `metaform twilio status`. With the bridge answering at its address, `metaform twilio check fix=true` sets the two webhooks below through Twilio's API; or set them by hand under the number's Configure tab in the Console (Phone Numbers > Manage > Active numbers > your number):
   - Voice Configuration: "A call comes in" > Webhook > the `voice` URL, `https://<address>/phone/voice`, HTTP POST. The PIN's `https://<address>/phone/pin` is named in the bridge's own answer; nothing is entered for it.
   - Messaging Configuration: "A message comes in" > Webhook > the `messaging` URL, `https://<address>/phone/sms`, HTTP POST.
   The call's audio opens `wss://<address>/phone/stream` by itself; nothing is entered for it.
5. In the US and Canada, texting from a 10-digit number needs A2P 10DLC registration (Messaging > Regulatory Compliance), or use a toll-free number with its verification. Calls need neither.
6. Turn the phone on, `metaform set --twilio-enabled`, start the bridge, and call your number from your own phone. `metaform twilio check` says at any time whether Twilio still sends the number's calls where the bridge answers; a temporary quick tunnel stops answering when it closes, and then every call hears Twilio's "application error" until the number is pointed at a lasting address (phone self-check, 2026-10-15, ticket 0a044360).

## A direct route

If you can forward a port from your router or firewall to this machine, Twilio can reach the bridge with no Node and no tunnel.

1. Forward a TCP port on your public address to port **7441** on this machine. The port Twilio uses is the one in `twilio_public_url`: 443 when it has none, or the one you write, such as `https://phone.example.com:7441`.
2. `metaform set --twilio-bind <this machine's LAN address>`, or `0.0.0.0` for every address.
3. Twilio's Media Stream needs `wss`, so the bridge must serve TLS. Either give it a certificate, `metaform set --twilio-certificate /path/bridge.pem`, one PEM file with the chain and the private key as Python's `ssl.load_cert_chain` reads it (Let's Encrypt's `fullchain.pem` and `privkey.pem` joined), for the name in `twilio_public_url`, from a public CA, since Twilio refuses a self-signed one; or put your own TLS terminator in front and leave the certificate empty.
4. Point a DNS name at your public address, set it as `twilio_public_url`, and run `metaform twilio check`.

Who can reach the open port: Twilio publishes fixed webhook source ranges only for its Static Proxy, part of the Security and Enterprise Editions: 3.80.20.0/25 (US1), 3.251.214.32/27 (IE1) and 3.26.81.96/27 (AU1), per twilio.com/docs/iam/twilio-editions/twilio-static-proxy, read 2026-10-15; Twilio says it may change them with 7 days' notice, so check before relying on them. With those you can allow only Twilio at your firewall. A standard account sends webhooks from a large range that changes, so you cannot allow-list it: the open port takes any connection, and what keeps everyone else out is the bridge's signature check, which refuses every request Twilio did not sign with your auth token, then the caller proof below.

Under WSL2, Linux is behind Windows's own NAT, so a port your router forwards reaches Windows, not the bridge. Turn on mirrored networking (`networkingMode=mirrored` under `[wsl2]` in `%UserProfile%\.wslconfig`, then `wsl --shutdown`), or forward it on Windows: `netsh interface portproxy add v4tov4 listenport=7441 connectport=7441 connectaddress=<the WSL address>`, and allow the port in Windows Defender Firewall. `metaform twilio check` says when it sees WSL2 with NAT networking on a direct route.

## Security model

The bridge faces the internet, so every way in is checked:

- **Signature.** Every webhook, the PIN's included, must carry `X-Twilio-Signature`, Twilio's HMAC-SHA1 of the public URL and the sorted POST parameters keyed with your auth token, compared in constant time; the URL is rebuilt from `twilio_public_url`, never the loopback one. An unsigned or forged request gets 403. The websocket upgrade is checked too when Twilio signs it.
- **The stream token.** The TwiML that connects a call to `/phone/stream` carries a one-time token as a `<Parameter>`. The stream's `start` message must hand it back, within a minute, for the same call SID; it is used once. Anything else is closed with 1008 before a byte reaches the agent.
- **Your numbers only.** A call from a number not in `twilio_owner_numbers` hears a short refusal and is hung up; a text from one is ignored. A call Metaform placed is bridged only when it is one this bridge placed, to your number, from your Twilio number, and only on its first webhook. Calls and texts are sent only to your numbers.
- **Caller ID is not proof.** Anyone can fake the number a call or text shows, and a call that gets through talks with an agent that can act on your machine. So `twilio_caller_proof` says what more it must show:
  - `attested-or-pin` (the default): a call whose carrier fully attested its caller ID, Twilio's `StirVerstat` `TN-Validation-Passed-A` (STIR/SHAKEN, US and Canadian carriers), is connected; any other is asked for the PIN on the keypad, ended with #, and connected only when it is right. Without a PIN set, an unattested call is refused.
  - `pin`: every call is asked for the PIN. The safest, and the choice outside North America, where calls are rarely attested.
  - `attested`: only fully attested calls; no PIN.
  - `caller-id`: the number alone, as before this setting. Anyone who fakes your number reaches your agent; choose it only knowingly.
  A text carries no attestation, so under any choice but `caller-id` it must start with the PIN and a space (`246810 what's waiting?`); the PIN is taken off before your agent reads it. A text that does not start with digits is ignored; one with the wrong PIN counts as a wrong PIN. Five wrong PINs within an hour, by call or text, and the PIN is not taken for an hour (an attested call still gets in under `attested-or-pin`). The PIN is `METAFORM_TWILIO_PIN` in the bridge's environment, never stored or shown; texts travel in the clear through the carriers, so a PIN you text is only as private as your texts.
- **Once only.** Twilio's signature has no time in it, so anyone who captured a signed webhook could send it again. Each CallSid and MessageSid is acted on once; a second webhook for one gets a hang-up or an empty answer, mints no stream token and reaches no agent. The SIDs are kept in `seen.txt`, so a restart does not forget them.
- **Rate limits.** Requests that fail the checks are counted by source and all together: five failures from one source in ten minutes, or more than 120 a minute from all sources, are answered 429 and no longer logged one by one. A request that passes the checks is never held back, so nobody can shut Twilio out by failing from the same address, as every client does behind the Node's relay, or by claiming its address in `X-Forwarded-For`. A stream refused because a call is already in progress is not a failure. Six of your texts answered a minute; one call at a time; calls Metaform places on its own at least `twilio_call_gap_minutes` apart (one held back by the gap, or by a call in progress, is placed once the gap allows, unless its signal clears first), and the same signal on the same ticket once an hour.
- **Loopback by default.** The bridge binds `twilio_bind`, `127.0.0.1` unless you choose a direct route, and is reached through `twilio_public_url`. It refuses to start unless that is https. The signature check holds on every route. `/control/call` and `/control/text`, your own `twilio call` and `twilio text`, answer only a request from this machine (loopback, or the address the bridge is bound to) that came through no proxy and carries the run file's control token.
- **Credentials.** Read from the environment for each use, never stored, logged or shown; `twilio status` names them only. The log has no transcript and no audio.
- **What this does not stop.** An agent with a shell, running as your account, can do whatever you can: change `twilio_owner_numbers` or `twilio_caller_proof` with `metaform set` (the next bridge start uses them), read the control token from the run file, or read the PIN and tokens from a process's environment. `person_only` holds over MCP and the page, and the phone's commands refuse an agent's session, but neither is a boundary against a shell. Keep agents that have a shell on a machine, or an account, that does not run the bridge, or leave the phone off while they work.

What leaves your machines: Twilio carries the call's audio and texts; ElevenLabs receives the text the agent speaks, and the audio too only when `twilio_hearing` is `elevenlabs`.

## Costs

Twilio bills the number monthly, each minute of a call (incoming and outgoing), Media Streams by the minute, and each text segment; ElevenLabs bills the characters spoken, and Scribe the audio heard. Check both price pages for your country. `twilio_call_gap_minutes` and leaving `twilio_call_when` empty keep Metaform from calling you more than you choose.
