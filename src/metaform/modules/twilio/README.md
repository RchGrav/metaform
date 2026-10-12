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
- `metaform twilio serve` (command line, write, open world): runs the bridge on `127.0.0.1:<twilio_port>` until stopped by Ctrl-C or SIGTERM (systemd, `docker stop`). It refuses to start while the phone is off, while `twilio_public_url` is not https, without the auth token, an owner number, a Twilio number, the voice module or a project, and when `twilio_caller_proof` is `pin` without a PIN.
- `metaform twilio call [to=<owner number>] [reason...]` (command line, write, open world): rings your phone now through the running bridge; your system agent opens with the reason.
- `metaform twilio text [to=<owner number>] <text...>` (command line, write, open world): texts your phone now.
- `metaform twilio test` (command line, read, task): a whole call simulated on this machine, with a scripted agent and voice and a recorder in place of Twilio's API: no network, no credential. It checks the refusals, the PIN asked of an unattested caller ID, a replayed webhook refused, the stream token, the greeting, the answer and barge-in, and reports the time from the end of your speech to the first audio back, `latency_ms`, as the voice's endpointing pause plus the bridge's own time.

Calls, texts and the bridge are the person's own: they are on the command line only, never MCP tools, and `call`, `text` and `serve` refuse to run in an agent's session (one whose runner set `METAFORM_SESSION`, `METAFORM_ROLE` or `METAFORM_WORK`). That refusal guards against an agent's mistakes; it is not a boundary. An agent with a shell runs as your account, so it can clear its environment, run `metaform set` on the phone's settings (`person_only` is enforced over MCP, not on the command line), or read the run file's control token. If you give agents a shell, the phone is only as safe as that shell; see the security model.

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
| `twilio_language` | auto | The language you speak on the phone. |
| `twilio_hearing` | server | Who hears you: `server` (Whisper on this machine) or `elevenlabs` (Scribe, which receives the audio). |
| `twilio_port` | 7441 | The loopback port; the Node routes `/phone/*` to 7441. |
| `twilio_project` | empty | Whose system agent answers; empty is the project of the folder the bridge runs in. |

## Events

Subscribes to `web.started`, which the web module publishes when `metaform web start` has the page running: with the phone on and set up, the bridge starts beside it, detached. While it runs, the bridge hears `map.changed` from other processes with `ctx.listen`; a payload carrying a raised dispatch `signal` of its project may place a call or send a text, and a change after which the project has an intake it lacked is `intake-finished`. It publishes nothing.

## Sync and async

`test` is a coroutine. `serve` runs its own event loop with uvicorn. The bridge is asyncio throughout; the voice module's functions, which block, run in threads: transcription in one thread per call fed by a queue, speech a chunk at a time.

## Layers

None, and no tables. The bridge keeps nothing about a call but its log lines.

## Lifecycle and cleanup

`serve` writes `<home>/run/twilio/twilio.json` (its pid, port, project and a one-time control token, readable by your account only) and removes it when it stops, by Ctrl-C or SIGTERM; `<home>/run/twilio/seen.txt` (readable by your account only) keeps the CallSids and MessageSids it acted on, the latest 100,000, so a webhook sent again is refused after a restart too; its log is `<home>/run/twilio/twilio.log`: when calls start and end, refusals, barge-ins and failures, never what was said and never a credential. A call that ends, by hang-up, `stop` or an error, stops its transcription and its speech and leaves the system agent running, its whole answer in the chat.

## Modules relied on

- `dispatch`, through its verbs `system` (start, resume or reuse your system agent), `message` (your words, as your own message) and `sessions` (its answer as it grows, and when its turn ends; each poll passes `since`, the thread's last line before your words, so it reads only the lines after them), and the signals its runners raise.
- `voice`, through what it provides as `voice` (`metaform.module.provided(folder, 'voice')`), only while it is enabled: `speak(folder, text, format='ulaw_8000', character=..., voice=twilio_voice)` streams the voice_tts engine's 8 kHz mu-law audio, in `twilio_voice` when it is set (`voice` is passed only then), and `transcribe_stream(folder, chunks, 'ulaw_8000', language=..., engine=twilio_hearing)` cuts the caller's audio into utterances at pauses and hears them. Speech is not duplicated here.
- `web`, for `web.started` and the mascot's name (`web_mascot`).

## Systems supported

Linux, macOS and Windows.

## Resources owned

The bridge's process while `serve` runs, its loopback port, its run file and log, one transcription thread per call in progress, and the tasks replying to your texts.

## Installed and direct wheel

The same in both: the bridge needs `starlette`, `uvicorn` and `websockets`, which an installed Metaform carries. Hearing on the server needs the voice extra; speaking needs `ELEVENLABS_API_KEY`.

## Demonstration

```bash
metaform twilio test                      # a simulated call: no Twilio, no engine, no agent
metaform set --twilio-number +15551234567 --twilio-owner-numbers +15557654321
metaform set --twilio-public-url https://alice.metaform.ing --twilio-call-when waiting-for-you --twilio-enabled
metaform twilio status                    # what is missing, and the URLs for Twilio
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
4. Run `metaform twilio status`. Under the number's Configure tab in the Console (Phone Numbers > Manage > Active numbers > your number):
   - Voice Configuration: "A call comes in" > Webhook > the `voice` URL, `https://<address>/phone/voice`, HTTP POST. The PIN's `https://<address>/phone/pin` is named in the bridge's own answer; nothing is entered for it.
   - Messaging Configuration: "A message comes in" > Webhook > the `messaging` URL, `https://<address>/phone/sms`, HTTP POST.
   The call's audio opens `wss://<address>/phone/stream` by itself; nothing is entered for it.
5. In the US and Canada, texting from a 10-digit number needs A2P 10DLC registration (Messaging > Regulatory Compliance), or use a toll-free number with its verification. Calls need neither.
6. Turn the phone on, `metaform set --twilio-enabled`, start the bridge, and call your number from your own phone.

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
- **Loopback only.** The bridge binds `127.0.0.1` and is reached only through `twilio_public_url`. It refuses to start unless that is https. `/control/call` and `/control/text`, your own `twilio call` and `twilio text`, answer only a loopback request that came through no proxy and carries the run file's control token.
- **Credentials.** Read from the environment for each use, never stored, logged or shown; `twilio status` names them only. The log has no transcript and no audio.
- **What this does not stop.** An agent with a shell, running as your account, can do whatever you can: change `twilio_owner_numbers` or `twilio_caller_proof` with `metaform set` (the next bridge start uses them), read the control token from the run file, or read the PIN and tokens from a process's environment. `person_only` holds over MCP and the page, and the phone's commands refuse an agent's session, but neither is a boundary against a shell. Keep agents that have a shell on a machine, or an account, that does not run the bridge, or leave the phone off while they work.

What leaves your machines: Twilio carries the call's audio and texts; ElevenLabs receives the text the agent speaks, and the audio too only when `twilio_hearing` is `elevenlabs`.

## Costs

Twilio bills the number monthly, each minute of a call (incoming and outgoing), Media Streams by the minute, and each text segment; ElevenLabs bills the characters spoken, and Scribe the audio heard. Check both price pages for your country. `twilio_call_gap_minutes` and leaving `twilio_call_when` empty keep Metaform from calling you more than you choose.
