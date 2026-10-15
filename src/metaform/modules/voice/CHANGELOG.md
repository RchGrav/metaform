# Changelog

Each change to the voice module, newest first.

## Unreleased

- Settings cleanup, 2026-10-15, ticket 0d9e3882: `voice_language` is the one language the person is heard in; `twilio_language` and `elevenlabs_scribe_language` merge into it. Once per home, as voice starts, a language stored in either becomes `voice_language` when that is not set, and the old rows are removed (`carry_language`, marked `carried:speech-language` in the home's meta). `voice_idle_minutes` is the constant `IDLE_MINUTES`, 10.
- `speak` takes an optional `voice`, a voice id of the engine's own, in `provides` `voice` and as the `voice speak` noun `voice`: it speaks in place of the character's voice with an engine whose `speak` takes a `voice` keyword, and any other engine speaks with the character's, so callers and engines written before it are unchanged. The twilio module's `twilio_voice` uses it.
- The voice module: speech to text on the web GUI with Whisper on this machine (faster-whisper, the optional `voice` and `voice-gpu` extras) or in the browser (transformers.js 4.3.0, WebGPU or WebAssembly), an engine another module provides as `voice.engine`, such as elevenlabs, a person's own OpenAI-compatible endpoint, or the browser's speech service; speech out with the browser's voices or a provided engine, a voice per mascot character; a wake phrase heard on the device; the verbs `status`, `models`, `transcribe`, `download` and `speak`; and `provides` `voice`, `speak`, `transcribe` and `transcribe_stream`, for a server-side caller such as a phone bridge.
