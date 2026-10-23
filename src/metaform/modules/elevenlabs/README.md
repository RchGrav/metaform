# elevenlabs

ElevenLabs's voices and its Scribe, brought to the voice module as one speech engine. ElevenLabs receives what it speaks and what it hears.

## Purpose

The voice module offers this engine beside its own while this module is enabled: ElevenLabs's voices speak the agent's replies when the person's `voice_tts` is `elevenlabs`, and Scribe hears them when their `voice_engine` is `elevenlabs`. Nothing is sent until the person chooses it, and only while `ELEVENLABS_API_KEY` is in the environment of the process that serves the page. Disabling the module withdraws the engine. Details: `metaform help elevenlabs`.

## Template version

The template changelog version this module started from: 0.2.0, with `provides`.

## Declaration

`SUPPORTED_OS` is Linux, macOS and Windows. `DEPENDENCIES` is empty: the standard library's HTTP client is enough. `SHIPS_DISABLED` is false: the engine is only offered, and nothing reaches ElevenLabs until the person chooses it and sets the key. `REMOTE_AGENT` is false.

### Toolbar items and panes

None. Its settings show in `metaform config`, the TUI, and the web GUI's settings under elevenlabs.

## Common base used

`metaform.module` for the declaration, `Provides` and `VoiceEngine`: the module provides `voice.engine`, a `VoiceEngine` named `elevenlabs` whose `transcribe`, `speak`, `ready` and `output` the voice module calls. It never imports voice, and voice never imports it. `metaform.settings` for the settings below.

## Prompts

`resources/prompts.xml` holds the module's line in the instructions agents read. Its `connect` line and `rules` are empty.

## Verbs

| Verb | Tool | What it returns | Effect |
|---|---|---|---|
| `metaform elevenlabs status` | `elevenlabs_status` | Whether the key is present, and the model, formats, voice settings and latency in use. Never the key. | read |
| `metaform elevenlabs models` | `elevenlabs_models` | The text-to-speech models the account can use, kept in the home as `elevenlabs_model`'s choices. | write, open world |
| `metaform elevenlabs voices` | `elevenlabs_voices` | Each mascot character's voice, and the voices on the account. | read, open world |
| `metaform elevenlabs speak -- <text>` | command line only | Text spoken into a file; never an agent's tool, since it spends the person's account. | write, open world |

The page and a phone bridge reach the engine through the voice module: `voice speak` and `voice transcribe`, and voice's `provides` `voice` for a server-side caller. The engine's `speak` takes the keyword `voice`, a voice id or a name on the account, passed when the caller names one, such as the twilio module's `twilio_voice`; it takes priority over an explicit character override in `elevenlabs_voices`, then the general `elevenlabs_voice`, then the built-in character voice.

## Settings

In the web settings, choose **ElevenLabs default voice** on Essentials when ElevenLabs speaks, or under Voice. Press **List voices** to fetch the account's voices, then choose one. This saves globally across page reloads and projects. **ElevenLabs character overrides (optional)** remains available under Voice for exceptions. Choosing a default does not select a speech engine or synthesize audio.

Every one is the module's own, `elevenlabs_*`, so they group together in the TUI.

| Setting | Default | What it does to the sound |
|---|---|---|
| `elevenlabs_model` | eleven_flash_v2_5 | The model that speaks; its choices are the account's models as last listed with `metaform elevenlabs models`, else ElevenLabs's published ones; finding them never asks ElevenLabs. Flash starts soonest, multilingual is the most natural, v3 the most expressive and slowest. |
| `elevenlabs_stability` | 50 | 0 to 100: low is livelier and less predictable, high is even and can sound flat. |
| `elevenlabs_similarity` | 75 | 0 to 100: how closely the voice keeps to its source, its timbre and accent and that recording's noise. |
| `elevenlabs_style` | 0 | 0 to 100: how much the source speaker's delivery is exaggerated; above 0 is slower to make. |
| `elevenlabs_speaker_boost` | on | More like the source speaker, at a little more time. |
| `elevenlabs_speed` | 100 | 70 to 120, percent of the voice's normal pace. |
| `elevenlabs_latency` | 1 | 0 to 4, optimize_streaming_latency: higher starts sooner and can mispronounce numbers and names. |
| `elevenlabs_voice` | empty | One default voice id or account voice name for every character without an override. Empty preserves the built-in character voices. |
| `elevenlabs_voices` | none | Optional `character=voice id or name` overrides, taking priority over the general default. |

Fixed, not settings (settings cleanup, 2026-10-15): the page's audio is `pcm_22050`, which plays as it arrives; a phone call's is `ulaw_8000`, the telephone's own encoding, which the phone bridge asks for itself; Scribe's model is `scribe_v1`, the released one. Scribe hears in the language voice passes it, the voice module's `voice_language`, or tells it itself when that is `auto`; `speak format=<format>` still writes any ElevenLabs format to a file.

The key is never a setting: it is read from `ELEVENLABS_API_KEY` in the server's environment for each request, sent only to ElevenLabs as `xi-api-key`, and never stored, logged, returned or sent to the page.

## Events

None.

## Sync and async

Every verb and engine function is synchronous; `speak` returns an iterator that streams ElevenLabs's audio as it is made.

## Layers

None. One file, `elevenlabs/models.json` in the Metaform home: the model ids `metaform elevenlabs models` last listed, in the account's order, the same in every folder as `elevenlabs_model` is global.

## Lifecycle and cleanup

No start or stop. The account's models and voices are kept in memory for ten minutes.

## Modules relied on

voice, which offers this engine and calls it; never by import.

## Systems supported

Linux, macOS and Windows.

## Resources owned

None but the HTTP requests it makes while a reply is spoken or heard.

## Installed and direct wheel

Both carry it; it needs nothing installed.

## Demonstration

```sh
export ELEVENLABS_API_KEY=...        # in the shell that starts the web GUI
metaform elevenlabs status
metaform elevenlabs voices
metaform set --elevenlabs-voice Daniel  # one voice for every character without an override
metaform set --voice-tts elevenlabs    # choose the paid engine separately
metaform elevenlabs speak character=owl -- "Hello there."
```
