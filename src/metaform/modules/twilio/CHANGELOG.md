# Changelog

Each change to the twilio module, newest first.

## Unreleased

- The twilio module: your own Twilio number answered by your system agent, your mascot, speaking, and calls or texts when an agent waits on you, looks stuck, reaches its budget or the intake finishes, as you choose; the verbs `status`, `serve`, `call`, `text` and `test`; its settings `twilio_*`; the bridge on `127.0.0.1:7441`, reached by Twilio at `/phone/voice`, `/phone/pin`, `/phone/sms` and `/phone/stream`; the caller's proof by STIR/SHAKEN attestation or `METAFORM_TWILIO_PIN`. Built as `phone` and renamed for the service it reaches before any release, so nothing is migrated: `phone_*` settings are `twilio_*`, `phone_twilio_number` is `twilio_number`, `METAFORM_PHONE_PIN` is `METAFORM_TWILIO_PIN`, and the run folder is `<home>/run/twilio`.
- `twilio_voice` speaks: an ElevenLabs voice id, or a voice's name on the account, passed to the voice module's `speak` as `voice`; empty, the mascot character's voice.
- The system agent's answer is polled with dispatch `sessions` `since`, so each poll reads only the thread's lines after the person's words.
