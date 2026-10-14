# Changelog

Each change to the elevenlabs module, newest first.

## Unreleased

- `elevenlabs_model`'s choices never ask ElevenLabs: they are the account's models as `metaform elevenlabs models` last listed them, kept for the project in the new table `listed_models`, else ElevenLabs's published ones. Before, `config --show`, help and every agent's `tools/list` sent the key to ElevenLabs and waited on it. `models` is now a write. A failed listing of models or voices is kept 60 seconds and raised again without a new request.
- The engine's `speak` takes the keyword `voice`, a voice id or a name on the account, which the voice module passes when a caller names one, such as the twilio module's `twilio_voice`; it speaks in place of the character's voice from `elevenlabs_voices`.
- The elevenlabs module: ElevenLabs's text to speech, streamed, and Scribe's speech to text, provided to the voice module as the `elevenlabs` voice engine through `provides`; its settings `elevenlabs_*`, the model from the account's own list, stability, similarity, style, speaker boost, speed, streaming latency, the page's and the phone's output formats, a voice per mascot character, Scribe's model and language; the verbs `status`, `models`, `voices` and `speak`. The key is read from `ELEVENLABS_API_KEY` in the environment only.
