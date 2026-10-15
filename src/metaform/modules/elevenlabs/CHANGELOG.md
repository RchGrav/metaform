# Changelog

Each change to the elevenlabs module, newest first.

## Unreleased

- Settings cleanup, 2026-10-15, ticket 0d9e3882: `elevenlabs_phone_format` is removed; it never took effect, since the phone bridge always asks for `ulaw_8000`. `elevenlabs_format` and `elevenlabs_scribe_model` are the constants `PAGE_FORMAT` (`pcm_22050`) and `SCRIBE_MODEL` (`scribe_v1`). `elevenlabs_scribe_language` merges into the voice module's `voice_language`, which voice already passed to Scribe; a value stored in the old key is carried there once.
- `elevenlabs_model`'s choices never ask ElevenLabs: they are the account's models as `metaform elevenlabs models` last listed them, kept in the home file `elevenlabs/models.json`, the same in every folder, else ElevenLabs's published ones. Before, `config --show`, help and every agent's `tools/list` sent the key to ElevenLabs and waited on it. `models` is now a write.
- The engine's `speak` takes the keyword `voice`, a voice id or a name on the account, which the voice module passes when a caller names one, such as the twilio module's `twilio_voice`; it speaks in place of the character's voice from `elevenlabs_voices`.
- The elevenlabs module: ElevenLabs's text to speech, streamed, and Scribe's speech to text, provided to the voice module as the `elevenlabs` voice engine through `provides`; its settings `elevenlabs_*`, the model from the account's own list, stability, similarity, style, speaker boost, speed, streaming latency, the page's and the phone's output formats, a voice per mascot character, Scribe's model and language; the verbs `status`, `models`, `voices` and `speak`. The key is read from `ELEVENLABS_API_KEY` in the environment only.
