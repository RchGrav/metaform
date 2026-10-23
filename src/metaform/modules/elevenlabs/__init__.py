"""elevenlabs: ElevenLabs's voices and its Scribe, brought to the voice module as one speech engine.

The voice module offers this engine beside its own, by `provides`, once this module is enabled: it speaks the agent's
replies with ElevenLabs's voices when the person's voice_tts is elevenlabs, and hears them with Scribe when their
voice_engine is elevenlabs. Either sends ElevenLabs what is spoken or heard. ElevenLabs's key is read from
ELEVENLABS_API_KEY in the environment of the process that serves the page, for each request; it is never stored in a
setting or a file, never logged and never sent to the page. Its advanced settings, the model, the voice's stability,
similarity, style, speaker boost and speed, and the streaming latency, are this module's own.

  status    whether the key is present, and the settings in use
  models    the text-to-speech models the account can use
  voices    each mascot character's voice, and the voices on the account
  speak     text spoken into an audio file, from the command line
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, cast

from metaform import home, settings
from metaform.module import Context, Module, Noun, Provides, Stop, Verb, VoiceEngine

from . import api

SUPPORTED_OS = ('linux', 'macos', 'windows')
DEPENDENCIES = ()  # the standard library's HTTP client is enough
SHIPS_DISABLED = False  # offered, never used until the person chooses it in voice_engine or voice_tts, with the key set
REMOTE_AGENT = False  # a person's voice on the page, not an agent's tool

# Each mascot character's default voice: one of ElevenLabs's default voices, so the mascot sounds like itself before
# the person chooses; elevenlabs_voice sets a general default and elevenlabs_voices overrides any character.
DEFAULT_VOICES = {
    'beetle': 'JBFqnCBsd6RMkjVDRZzb', 'comet': 'cgSgspJ2msm6clMCkdW9', 'crystal': 'Xb7hH8MSUJpSbSDYk0k2',
    'cubebot': 'cjVigY5qzO86Huf0OWal', 'drone': 'N2lVS1w4EtoT3dr4eOWO', 'gearling': 'IKne3meq5aSn9XLyUdCD',
    'jelly': 'pFZP5JQG7iQjIQuC4Bku', 'kite': 'FGY2WhTYpPnrIDTdsKH5', 'moth': 'XB0fDUnXU5powFXDhCwa',
    'mushroom': 'pqHfZKP75CvOlQylNhV4', 'owl': 'onwK4e9ZLuTAKqWW03F9', 'plane': 'TX3LPaxmHKxFdv7VOQHJ',
    'puffer': '9BWtsMINqrJLrRacOk9x', 'seahorse': 'XrExE9yKIg1WjnnlVkGX', 'slime': 'CwhRBWXzGAHq8TQ4Fs17',
    'snail': 'nPczCjzI2devNBz1zQrb', 'wisp': 'SAz9YHcvj6GT2YYXdXww',
}
FALLBACK = 'JBFqnCBsd6RMkjVDRZzb'  # George, for a mascot that is none of these
# The audio streamed to the page: raw samples play as they arrive, so the reply starts at once; 22,050 a second is the
# middle of ElevenLabs's pcm rates. A call always takes the telephone's own encoding, ulaw_8000, which the phone bridge
# asks for itself (twilio/engines.py FORMAT). Settings cleanup 2026-10-15: each had one right answer.
PAGE_FORMAT, PHONE_FORMAT = 'pcm_22050', 'ulaw_8000'
# Scribe's released model; scribe_v1_experimental changes without notice, so it is never what a person's speech goes to.
SCRIBE_MODEL = 'scribe_v1'


def _listed() -> Path:
    """The account's model ids as `metaform elevenlabs models` last listed them, in the account's order, kept in the
    home: elevenlabs_model's choices read them, and never ElevenLabs, because config --show, help and every agent's
    tool list compute those choices. One file for the home, as the setting is global."""
    return home.home() / 'elevenlabs' / 'models.json'


def _models(ctx: Context | None = None) -> list[str]:
    """The models to choose from: the account's as last listed with metaform elevenlabs models, else the ones
    ElevenLabs publishes. Never a request to ElevenLabs."""
    try:
        listed: Any = json.loads(_listed().read_text(encoding='utf-8'))
    except (OSError, ValueError):
        listed = None
    if isinstance(listed, list) and listed:
        return [str(one) for one in cast(list[Any], listed)]
    return list(api.MODELS)


def _check_voices(value: Any, folder: Path) -> list[str] | None:
    entries = [str(one) for one in cast(list[Any], value or [])]
    wrong = [one for one in entries if '=' not in one or one.split('=', 1)[0] not in DEFAULT_VOICES
             or not one.split('=', 1)[1].strip()]
    said = f'elevenlabs_voices takes character=voice for the characters {", ".join(DEFAULT_VOICES)}; not {", ".join(wrong)}.'
    return [said] if wrong else None


settings.choice('elevenlabs_model', _models, 'eleven_flash_v2_5', scope='global',
                help='The ElevenLabs model that speaks: the account\'s models as last listed with metaform elevenlabs '
                     'models, else ElevenLabs\'s published ones.',
                details='eleven_flash_v2_5 starts speaking soonest and costs least; eleven_turbo_v2_5 is a little '
                        'richer; eleven_multilingual_v2 is the most natural across languages and slower to start; '
                        'eleven_v3 is the most expressive and the slowest.',
                label='ElevenLabs model', heading='ElevenLabs')
settings.number('elevenlabs_stability', 50, min=0, max=100, scope='global',
                help='How steady the voice is, 0 to 100: low is livelier and less predictable.',
                details='Low values let the voice vary its tone from line to line, more emotional and sometimes '
                        'erratic; high values keep it even and calm, and can sound flat.',
                category='advanced', unit='%')
settings.number('elevenlabs_similarity', 75, min=0, max=100, scope='global',
                help='How closely the voice keeps to the original, 0 to 100.',
                details='High values hold the voice to its source recording, its timbre and accent, and can carry '
                        'that recording\'s noise too; low values let it drift for a cleaner sound.',
                category='advanced', unit='%')
settings.number('elevenlabs_style', 0, min=0, max=100, scope='global',
                help='How much of the voice\'s own style is exaggerated, 0 to 100; 0 is fastest.',
                details='Above 0 the voice leans into the delivery of its source speaker, more dramatic and slower '
                        'to make; 0 keeps it plain and adds no time.',
                category='advanced', unit='%')
settings.boolean('elevenlabs_speaker_boost', True, scope='global',
                 help='Boost the likeness to the original speaker.',
                 details='On, the voice sounds more like its source speaker, at a little more time per reply.',
                 category='advanced')
settings.number('elevenlabs_speed', 100, min=70, max=120, scope='global',
                help='How fast the voice speaks, as a percent of its normal pace, 70 to 120.',
                category='advanced', unit='%')
settings.number('elevenlabs_latency', 1, min=0, max=4, scope='global',
                help='Streaming latency, 0 to 4: higher starts speaking sooner and can mispronounce numbers and names.',
                details='ElevenLabs\'s optimize_streaming_latency. 0 is its best quality; 1 to 3 trade more of it for '
                        'a sooner first sound; 4 also skips the reading of numbers and dates as words.',
                label='Latency optimization', category='advanced')
settings.text('elevenlabs_voice', '', scope='global',
              help='The default voice for every character without an override.',
              details='A voice id or name on your ElevenLabs account. List voices to choose one. Empty keeps each '
                      'character\'s built-in voice. Choosing a voice does not turn on ElevenLabs.',
              label='ElevenLabs default voice', heading='ElevenLabs')
settings.items('elevenlabs_voices', [], scope='global', exclusive='=', check=_check_voices,
               help='A voice for a mascot character, as character=voice id or name, such as owl=Daniel.',
               details='The voice is an id or a name of a voice on your ElevenLabs account; metaform elevenlabs '
                       'voices lists them. Optional: a character not named uses elevenlabs_voice, or its built-in '
                       'voice when no general default is set.',
               label='ElevenLabs character overrides (optional)', heading='ElevenLabs')


def ready(ctx: Context) -> str | None:
    """None while the engine can be used; otherwise why not, with the next step."""
    return None if api.available() else \
        f'{api.KEY} is not in the environment of the process that serves the page; set it there and start it again.'


def _need(ctx: Context) -> None:
    why = ready(ctx)
    if why:
        raise Stop(why, f'export {api.KEY}=... before metaform web start')


def voice_of(ctx: Context, character: str | None, voice: str | None = None) -> str:
    """The voice id a character speaks with: `voice` when a caller names one, such as twilio_voice, else the person's
    elevenlabs_voices override, else elevenlabs_voice; an id or a name on the account, else the built-in default."""
    chosen = dict(entry.split('=', 1) for entry in cast(list[str], ctx.setting('elevenlabs_voices') or []) if '=' in entry)
    given = voice or chosen.get(character or '') or ctx.setting('elevenlabs_voice')
    if given:
        if re.fullmatch(r'[A-Za-z0-9]{16,40}', given):
            return given
        found = api.voice_named(given)
        if found is None:
            raise Stop(f'No voice {given} on your ElevenLabs account.', 'metaform elevenlabs voices')
        return found
    return DEFAULT_VOICES.get(character or '', FALLBACK)


def voice_settings(ctx: Context) -> dict[str, Any]:
    return {'stability': int(ctx.setting('elevenlabs_stability')) / 100,
            'similarity_boost': int(ctx.setting('elevenlabs_similarity')) / 100,
            'style': int(ctx.setting('elevenlabs_style')) / 100,
            'use_speaker_boost': bool(ctx.setting('elevenlabs_speaker_boost')),
            'speed': int(ctx.setting('elevenlabs_speed')) / 100}


def output_of(ctx: Context, format: str) -> str:
    """The ElevenLabs format a speak in `format` streams: page and phone are PAGE_FORMAT and PHONE_FORMAT."""
    return PAGE_FORMAT if format == 'page' else PHONE_FORMAT if format == 'phone' else format


def speak_engine(ctx: Context, text: str, character: str | None = None, format: str = 'page', *,
                 voice: str | None = None) -> Any:
    """The voice engine's speak: `text` in the character's voice as audio chunks, or in `voice`, a voice id or a name
    on the account, when the caller names one; `format` is 'page' or 'phone', PAGE_FORMAT and PHONE_FORMAT, or an
    ElevenLabs output format such as ulaw_8000."""
    _need(ctx)
    output = output_of(ctx, format)
    try:
        return api.tts(text, voice_of(ctx, character, voice), model=str(ctx.setting('elevenlabs_model')), output=output,
                       latency=int(ctx.setting('elevenlabs_latency')), settings=voice_settings(ctx))
    except OSError as error:
        raise Stop(str(error), 'metaform elevenlabs status') from None


def transcribe_engine(ctx: Context, path: Path, language: str | None = None) -> dict[str, Any]:
    """The voice engine's transcribe: an audio file's text from Scribe, which receives the audio, in the language voice
    passes, its voice_language, or Scribe's own guess with none."""
    _need(ctx)
    try:
        return api.scribe(path, model=SCRIBE_MODEL, language=language)
    except OSError as error:
        raise Stop(str(error), 'metaform elevenlabs status') from None


ENGINE = VoiceEngine(
    name='elevenlabs', summary="ElevenLabs's voices and its Scribe.",
    sends='ElevenLabs receives the text it speaks and the audio it hears.',
    transcribe=transcribe_engine, speak=speak_engine, ready=ready, formats=api.FORMATS, output=output_of)


def status(ctx: Context) -> dict[str, Any]:
    return {'key': api.available(), 'ready': ready(ctx) is None, 'why': ready(ctx),
            'model': ctx.setting('elevenlabs_model'), 'format': PAGE_FORMAT, 'phone_format': PHONE_FORMAT,
            'voice_settings': voice_settings(ctx), 'latency': ctx.setting('elevenlabs_latency'),
            'scribe_model': SCRIBE_MODEL}


def list_models(ctx: Context) -> dict[str, Any]:
    """The account's models from ElevenLabs, kept in the home as elevenlabs_model's choices."""
    _need(ctx)
    try:
        found = api.models()
    except OSError as error:
        raise Stop(str(error), 'metaform elevenlabs status') from None
    if found:
        home.mkdir_private(_listed().parent)
        home.write_private(_listed(), json.dumps([one['model_id'] for one in found]))
    return {'models': found}


def list_voices(ctx: Context) -> dict[str, Any]:
    chosen = dict(entry.split('=', 1) for entry in cast(list[str], ctx.setting('elevenlabs_voices') or []) if '=' in entry)
    general = ctx.setting('elevenlabs_voice')
    characters = {name: chosen.get(name) or general or default for name, default in DEFAULT_VOICES.items()}
    account: list[dict[str, Any]] | None = None
    if api.available():
        try:
            account = api.voices()
        except OSError as error:
            raise Stop(str(error), 'metaform elevenlabs status') from None
    return {'default': general, 'characters': characters, 'account': account,
            'next': None if account is not None else f'{api.KEY} in the environment lists your account\'s voices'}


def speak(ctx: Context) -> dict[str, Any]:
    """Text spoken into a file, from the command line; the page and a phone bridge reach the engine through voice."""
    given: Any = ctx.nouns['text']
    text = ' '.join(str(one) for one in cast(list[Any], given)) if isinstance(given, (list, tuple)) else str(given)
    output = str(ctx.nouns.get('format') or PAGE_FORMAT)
    audio = speak_engine(ctx, text, str(ctx.nouns.get('character') or '') or None, output)
    target = Path(str(ctx.nouns.get('file') or f'speech.{output.split("_", 1)[0]}')).expanduser()
    if home.is_home_path(target):
        home.mkdir_private(target.parent)
        home.write_private(target, b'')
    with target.open('wb') as out:
        for chunk in audio:
            out.write(chunk)
    return {'file': str(target), 'bytes': target.stat().st_size, 'format': output}


MODULE = Module(
    id='elevenlabs',
    summary="ElevenLabs's voices and Scribe, as a speech engine for voice; it receives what it speaks and hears.",
    purpose='Brings ElevenLabs to the voice module: its voices speak replies and its Scribe hears the person, each '
            'only when the person chooses elevenlabs in voice_tts or voice_engine, with ELEVENLABS_API_KEY in the '
            'server\'s environment. Details: metaform help elevenlabs.',
    details='Its advanced settings, elevenlabs_*, shape the sound: model, stability, similarity, style, speaker '
            'boost, speed, streaming latency, and the formats for the page and for a phone call.',
    verbs=(
        Verb('status', status, 'Show whether the ElevenLabs key is present and the settings in use.', effect='read', surfaces=('cli',)),
        Verb('models', list_models, 'List the text-to-speech models your ElevenLabs account can use.', effect='write',
             open_world=True, surfaces=('cli',)),  # writes the listing it keeps as elevenlabs_model's choices
        Verb('voices', list_voices, "List each mascot character's voice and the voices on your ElevenLabs account.",
             effect='read', open_world=True, surfaces=('cli',)),
        Verb('speak', speak, 'Speak text with ElevenLabs into an audio file; ElevenLabs receives the text.',
             nouns=(Noun('character', 'The mascot character whose voice speaks it.', required=False),
                    Noun('format', 'The output format, such as mp3_44100_128, pcm_16000 or ulaw_8000.', required=False),
                    Noun('file', 'The file to write; speech.<format> by default.', required=False),
                    Noun('text', 'What to say.', many=True)),
             examples=(('metaform elevenlabs speak character=owl -- "Hello there."', 'Writes speech.pcm.'),),
             surfaces=('cli',), effect='write', open_world=True),  # not an agent's to spend the person's account on
    ),
    subscriptions=(),
    start=None,
    stop=None,
    status=None,
    tables=None,
    data=None,
    node_read=None,
    node_count=None,
    work_read=None,
    item_read=None,
    items_at=None,
    item_kinds=(),
    toolbar=(),
    panes=(),
    provides=(Provides('voice.engine', ENGINE),),
    settings_category='voice',
)
