# voice

Talk to Metaform instead of typing, and hear the agent you talk to answer in your mascot's voice.

## Purpose

A mic sits beside every box where a person writes to an agent on the web GUI: the chat dock's compose box, the mascot's reply field, and any field marked `data-voice`. What the person says appears in the box as they say it, editable, and is sent when they press Enter, or after a pause with `voice_send auto`. With the wake phrase on, the person can speak to their system agent hands-free, and the agent's replies are spoken. Whisper hears them on their own machine by default, so the audio stays on their devices unless they choose a service that says it sends it. Details: `metaform help voice`.

## Template version

The template changelog version this module started from: 0.2.0.

## Declaration

`SUPPORTED_OS` is Linux, macOS and Windows: every engine runs on each. `DEPENDENCIES` is empty, because the page's own engine needs nothing on the server; the server engine is the optional extra `voice` (faster-whisper), and `voice-gpu` adds NVIDIA's cuBLAS and cuDNN wheels for CUDA. `SHIPS_DISABLED` is false: everybody who types to an agent can talk to it instead. `REMOTE_AGENT` is false: a person's voice belongs to the page, not to an agent on a hosted sandbox.

### Toolbar items and panes

None. The mic, its level meter and the wake indicator are drawn by the page, `web/page/voice.js`, beside the boxes they serve.

## Common base used

`metaform.module` for the declaration, `Context` and `Stop`, and for engines other modules bring: `provided(folder, 'voice.engine')` finds each `VoiceEngine` an enabled module provides, such as elevenlabs's, and voice provides `voice`, its own speak and transcribe, for a server-side caller; `metaform.settings` for the settings below; `metaform.home` for the models folder, `<home>/models`, the only place a model is written, and the run folder that holds an utterance while it is heard.

## Prompts

`resources/prompts.xml` holds the module's line in the instructions agents read. Its `connect` line and `rules` are empty: voice is the person's, and an agent needs nothing from it.

## Verbs

| Verb | Tool | What it returns | Effect |
|---|---|---|---|
| `metaform voice status` | `voice_status` | The engine in use and why, the device, the model, whether it is downloaded and loaded, and how to install the extra when it is not. | read |
| `metaform voice models` | `voice_models` | Each engine's Whisper models, their sizes and whether they are downloaded. | read |
| `metaform voice transcribe <file>` | `voice_transcribe` | An audio file's text and segments, with the server engine, ElevenLabs's Scribe or the person's endpoint; `partial=true` is a quick pass. | read, open world |
| `metaform voice download` | `voice_download` | A model fetched once into `<home>/models`; a caution verb, since it can be 1.6 GB. | write, open world |
| `metaform voice speak -- <text>` | command line only | Text spoken into a file by the `voice_tts` engine a module brings; never an agent's tool, since it spends the person's account. | write, open world |

### Engines that hear

`voice_engine` chooses, and `voice status` and the mic's tooltip say which is in use and why.

- **auto**, the default: Whisper on this machine's server when the voice extra is installed and the machine serves speech well, an NVIDIA GPU or 8 or more CPU cores; otherwise Whisper in the browser.
- **browser**: Whisper in the page's own worker with transformers.js 4.3.0, on WebGPU where the browser has it and WebAssembly everywhere else: macOS, Windows, Linux without a GPU, phones, tablets, and a hosted Metaform Node too small to run a model. No server install.
- **server**: faster-whisper (CTranslate2) here: CUDA float16 on NVIDIA, else CPU int8. The model stays loaded in the web server between utterances and is let go after `voice_idle_minutes`.
- **an engine a module brings**: each enabled module that provides a `voice.engine` adds its own choice, and says where it sends the audio. The elevenlabs module brings `elevenlabs`, ElevenLabs's Scribe: **your audio is sent to ElevenLabs.**
- **endpoint**: any OpenAI-compatible `/audio/transcriptions` URL, `voice_endpoint_url`, such as a Whisper server of your own. **Your audio is sent there.**
- **browser-speech**: the browser's own speech service. **Your audio is sent to the browser's vendor.** Firefox has none.
- **off** hides the mic.

whisper.cpp and mlx-whisper are not used: faster-whisper already covers CPUs on every system and CUDA, and the in-browser engine covers every machine without the extra, Apple Silicon on WebGPU among them. A third engine would be a second set of models, builds and bugs for a speed-up only some Macs would see.

### Speech out

`voice_tts` is **browser**, the default, the system's own voices through speechSynthesis on the device; an engine a module brings, such as **elevenlabs**, streamed through the server (raw PCM plays as it arrives) and **receiving the text spoken**, with its own settings in its own module; or **off**. Each mascot character has its own voice: a pitch and pace on the system's voices, which `voice_voices` can name; an engine a module brings gives each its own voice too. `voice_speak` says when replies are spoken: while the chat is put away (`minimized`, the default), `always`, or `never`.

### The wake phrase

`voice_wake`, off by default, keeps the microphone open while a small indicator at the foot of the page says so. Each stretch of speech has only its first 2.5 seconds heard, on this device, for the phrase, `voice_wake_phrase` or the mascot's name; nothing else is kept or sent. What follows the phrase goes to the person's system agent. It needs a local engine. Ctrl+Shift+Space turns it on and off for the page.

### For a phone bridge, and any server-side caller

Voice provides `voice`, found with `metaform.module.provided(folder, 'voice')` and never by import; `service.py` documents it. `speak(folder, text, format='phone', character=None, engine=None, voice=None)` streams audio chunks from the `voice_tts` engine, `ulaw_8000` for a call with elevenlabs; `voice`, optional, is a voice id of the engine's own, such as the twilio module's `twilio_voice`, spoken in place of the character's voice by an engine whose `speak` takes a `voice` keyword (elevenlabs does, as an id or a name on the account), while an engine that takes none speaks with the character's voice, so a caller written before it, and an engine written before it, work as they did; `voice speak voice=<id>` does the same on the command line; `transcribe(folder, path, language=None, engine=None)` hears a file; `transcribe_stream(folder, chunks, format='ulaw_8000', language=None, engine=None, partials=True)` cuts a stream of mu-law 8 kHz or 16-bit PCM chunks into utterances at pauses and yields `{'text', 'final'}`, partials from Whisper here, finals from any engine. Local Whisper stays in voice: it is the engine the person owns, with no service behind it.

## Settings

| Setting | Default | What it does |
|---|---|---|
| `voice_engine` | auto | Who hears: auto, browser, server, an engine a module brings, endpoint, browser-speech or off. Person only. |
| `voice_model` | auto | The server model: large-v3-turbo on a GPU, small on a CPU; or tiny, base, small, medium, large-v3-turbo. |
| `voice_browser_model` | auto | The browser model: base; or tiny, base, small. |
| `voice_device` | auto | The server engine on cuda or cpu. |
| `voice_language` | auto | A language code, or auto. |
| `voice_send` | review | review leaves the text for Enter; auto sends after a pause. |
| `voice_send_audio` | never | accepted sends the recording beside its transcript to a chat agent whose session declares audio. Person only. |
| `voice_idle_minutes` | 10 | Minutes the server keeps its model loaded; 0 keeps it. |
| `voice_max_seconds` | 120 | The longest utterance heard at once. |
| `voice_endpoint_url`, `voice_endpoint_model`, `voice_endpoint_key_env` | empty, whisper-1, empty | The person's own transcription endpoint, and the environment variable that holds its key. Person only. |
| `voice_tts` | browser | Who speaks replies: browser, an engine a module brings, or off. Person only. |
| `voice_speak` | minimized | When replies are spoken. |
| `voice_voices` | none | `character=browser voice name` for any mascot character. |
| `voice_wake`, `voice_wake_phrase` | off, the mascot's name | The wake phrase. Person only. |

## Events

None published or heard.

## Sync and async

Every verb is synchronous. `transcribe` and `download` are marked `task=True`, since a cold model or a large download takes a while.

## Layers

None, and no tables. Nothing a person says is stored: an utterance is written to `<home>/run/voice/heard` while it is heard and removed at once; a clip kept for an agent that takes audio is removed when the agent's runner reads it, or after an hour.

## Lifecycle and cleanup

`stop` lets the loaded model go. A model is let go after `voice_idle_minutes` without an utterance.

## Modules relied on

elevenlabs, and any module that provides a `voice.engine`, found through `provided` and never imported; web, whose server runs these verbs for the page at `/api/voice/*` in its own process, so the model stays loaded there; dispatch, whose `message` takes an `audio=` clip and sends it as an ACP audio block only where the agent's session declares `promptCapabilities.audio`.

## Systems supported

Linux, macOS and Windows. CUDA needs NVIDIA hardware on Linux or Windows with the `voice-gpu` extra.

## Resources owned

`<home>/models/whisper/<model>` and `<home>/models/browser/` (the browser engine's ONNX models and ONNX Runtime's WebAssembly binary, fetched with the first browser model and checked by its SHA-256); the loaded model in the web server's memory.

## Installed and direct wheel

Both carry the module and the browser engine. The server engine needs `pip install 'metaform[voice]'` (`'metaform[voice-gpu]'` with an NVIDIA GPU); from a source checkout, `uv sync --extra voice`. `voice status` says so when it is missing.

## Demonstration

```sh
metaform voice status
metaform voice download model=small --confirm
metaform voice transcribe ~/clip.wav
metaform set --voice-send auto --voice-wake
metaform web start
```
