"""voice: speech to text, so a person can talk to Metaform instead of typing.

The web GUI's mic, and push-to-talk, turn what the person says into text in the box they speak into. Which engine
hears them is the person's `voice_engine`: auto runs Whisper on this machine's server when it serves speech well, a GPU
or a strong CPU with the voice extra installed, and otherwise in the browser itself, with transformers.js; either way
the audio never leaves the person's own machines. A transcription URL of their own and the browser's speech service
are there too, off unless chosen, each said plainly to send the audio away.

  status      which engine is in use and why, the machine's device, the model and whether it is loaded
  models      the Whisper models of each engine, their sizes and whether they are downloaded
  transcribe  an audio file's text and segments, with the server engine or the person's endpoint
  download    a model, once, into the Metaform home's models folder; the page asks the person first
"""
from __future__ import annotations

import inspect
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlsplit

from metaform import home, settings
from metaform.module import Context, Module, Noun, Provides, Stop, Verb, VoiceEngine, provided

from . import engine, models, relay, service, speech

SUPPORTED_OS = ('linux', 'macos', 'windows')
DEPENDENCIES = ()  # faster-whisper is the optional extra `voice`; the browser engine needs nothing here
SHIPS_DISABLED = False
REMOTE_AGENT = False  # a person's voice, on the page; nothing an agent on a hosted sandbox uses

OWN = ('auto', 'browser', 'server', 'endpoint', 'browser-speech', 'off')  # the engines voice runs itself


def engines(folder: Path) -> dict[str, VoiceEngine]:
    """The speech engines enabled modules provide, by name: elevenlabs's among them when it is on."""
    return {one.name: one for _, one in provided(folder, 'voice.engine') if isinstance(one, VoiceEngine)}


def _listeners(ctx: Any = None) -> list[str]:
    folder = ctx.folder if ctx is not None else Path.cwd()
    return [*OWN[:3], *(name for name, one in engines(folder).items() if one.transcribe), *OWN[3:]]


def _speakers(ctx: Any = None) -> list[str]:
    folder = ctx.folder if ctx is not None else Path.cwd()
    return ['browser', *(name for name, one in engines(folder).items() if one.speak), 'off']
SERVER_MODELS = ('auto', *models.SERVER)
BROWSER_MODELS = ('auto', *models.BROWSER_NAMES)
LANGUAGE = re.compile(r'^(auto|[a-z]{2,3})$')
# The languages Whisper hears, by the codes its tokenizer names them with (openai/whisper, whisper/tokenizer.py), in
# its order: the choices of voice_language, which every engine here is told.
LANGUAGES = ('en', 'zh', 'de', 'es', 'ru', 'ko', 'fr', 'ja', 'pt', 'tr', 'pl', 'ca', 'nl', 'ar', 'sv', 'it', 'id', 'hi',
             'fi', 'vi', 'he', 'uk', 'el', 'ms', 'cs', 'ro', 'da', 'hu', 'ta', 'no', 'th', 'ur', 'hr', 'bg', 'lt', 'la',
             'mi', 'ml', 'cy', 'sk', 'te', 'fa', 'lv', 'bn', 'sr', 'az', 'sl', 'kn', 'et', 'mk', 'br', 'eu', 'is', 'hy',
             'ne', 'mn', 'bs', 'kk', 'sq', 'sw', 'gl', 'mr', 'pa', 'si', 'km', 'sn', 'yo', 'so', 'af', 'oc', 'ka', 'be',
             'tg', 'sd', 'gu', 'am', 'yi', 'lo', 'uz', 'fo', 'ht', 'ps', 'tk', 'nn', 'mt', 'sa', 'lb', 'my', 'bo', 'tl',
             'mg', 'as', 'tt', 'haw', 'ln', 'ha', 'ba', 'jw', 'su', 'yue')


def _check_language(value: Any, folder: Path) -> list[str] | None:
    return None if isinstance(value, str) and LANGUAGE.match(value) else \
        ['voice_language is auto or a language code, such as en, de or ja.']


def _check_url(value: Any, folder: Path) -> list[str] | None:
    if value in ('', None):
        return None
    parts = urlsplit(str(value))
    return None if parts.scheme in ('http', 'https') and parts.netloc else \
        ['voice_endpoint_url is an http(s) URL ending in /audio/transcriptions, or empty.']


# Where the person's audio goes.
settings.choice('voice_engine', _listeners, 'auto', scope='global',
                help='Who turns your speech into text: auto, browser, server, an engine a module brings, endpoint, '
                     'browser-speech or off.',
                details='auto runs Whisper on this machine\'s server when the voice extra is installed and it has '
                        'an NVIDIA GPU or a strong CPU, and otherwise in your browser; the audio stays on your '
                        'devices either way. browser always runs Whisper in the page; server always on this '
                        'machine. An engine a module brings, such as elevenlabs, says where it sends your audio. '
                        'endpoint SENDS YOUR AUDIO to the URL in voice_endpoint_url. '
                        'browser-speech uses the '
                        "browser's own speech service, which SENDS YOUR AUDIO to the browser's vendor (Google for "
                        'Chrome, Apple for Safari). off hides the mic.',
                label='Hears you with', heading='Listening')
settings.choice('voice_model', list(SERVER_MODELS), 'auto', scope='global',
                help='The server engine\'s Whisper model: auto, ' + ', '.join(models.SERVER) + '.',
                details='auto is large-v3-turbo on an NVIDIA GPU and small on a CPU. Each downloads once into the '
                        'Metaform home\'s models folder, after you agree to its size.',
                label='Whisper model on this machine', heading='Listening')
settings.choice('voice_browser_model', list(BROWSER_MODELS), 'auto', scope='global',
                help="The browser engine's Whisper model: auto, " + ', '.join(models.BROWSER_NAMES) + '.',
                details='auto is base. It downloads once, after you agree to its size, into the Metaform home, and '
                        'the browser keeps a copy; the audio never leaves the device.',
                label='Whisper model in the browser', heading='Listening')
# The one language the person is heard in: the page, the phone (twilio) and Scribe (elevenlabs) all take it from here,
# settings cleanup 2026-10-15, which merged twilio_language and elevenlabs_scribe_language into it.
settings.choice('voice_language', ['auto', *LANGUAGES], 'auto', scope='global', check=_check_language,
                help='The language you speak, as a code such as en, or auto to let the engine tell, on the page and '
                     'on the phone.',
                label='Language you speak', heading='Listening')
settings.choice('voice_send', ['review', 'auto'], 'review', scope='global',
                help='After you speak: review leaves the text in the box for Enter; auto sends it after a pause.',
                label='Send what you said', heading='Listening')
settings.choice('voice_send_audio', ['never', 'accepted'], 'never', scope='global',
                help='Send your recorded voice itself to a chat agent too: never, or when the agent accepts audio.',
                details='accepted sends the recording beside its transcript as an ACP audio block, only to an agent '
                        'whose session declares that it takes audio. The transcript is in the thread either way.',
                label='Send your audio to agents', heading='Listening')
settings.choice('voice_device', ['auto', 'cuda', 'cpu'], 'auto', scope='global',
                help='Where the server engine runs Whisper: auto (an NVIDIA GPU when there is one), cuda or cpu.',
                label='Whisper runs on', category='advanced')
settings.number('voice_max_seconds', 120, min=5, max=600, scope='global',
                help='The longest utterance heard at once, in seconds; anything longer is refused.',
                label='Longest recording', category='advanced')
settings.text('voice_endpoint_url', '', scope='global', check=_check_url,
              help='Your own OpenAI-compatible transcription URL, for voice_engine endpoint. It receives your audio.',
              details='Such as http://127.0.0.1:8000/v1/audio/transcriptions for a Whisper server of your own, or '
                      'https://api.openai.com/v1/audio/transcriptions for a service, which then receives your audio.',
              label='Transcription endpoint', category='advanced', heading='Your endpoint')
settings.text('voice_endpoint_model', 'whisper-1', scope='global',
              help='The model name sent to your transcription endpoint.',
              label='Endpoint model', category='advanced', heading='Your endpoint')
settings.text('voice_endpoint_key_env', '', scope='global',
              help='The environment variable that holds your endpoint\'s key, such as OPENAI_API_KEY; empty sends none.',
              details='The key is read from the environment of the process that serves the page and sent only to '
                      'voice_endpoint_url; it is never stored by Metaform or shown to the page.',
              label='Endpoint key variable', category='advanced', heading='Your endpoint')


def _check_voices(value: Any, folder: Path) -> list[str] | None:
    entries = [str(one) for one in cast(list[Any], value or [])]
    wrong = [one for one in entries if '=' not in one or one.split('=', 1)[0] not in speech.CHARACTERS
             or not one.split('=', 1)[1].strip()]
    said = f'voice_voices takes character=voice for the characters {", ".join(speech.CHARACTERS)}; not {", ".join(wrong)}.'
    return [said] if wrong else None


# Speech out: the agent the person talks to, their mascot, answers aloud. The browser's own voices run on the device;
# ElevenLabs only where its key is in the server's environment, and it receives the text spoken.
settings.choice('voice_tts', _speakers, 'browser', scope='global',
                help="Who speaks the agent's replies: browser (your system's own voices), an engine a module brings, "
                     'or off.',
                details='browser speaks with the voices your system has, on the device. An engine a module brings, '
                        'such as elevenlabs, SENDS THE TEXT SPOKEN to its service and streams the audio back.',
                label='Speaks with', heading='Speaking', essential=70)
settings.choice('voice_speak', ['minimized', 'always', 'never'], 'minimized', scope='global',
                help="When replies are spoken: minimized (while the chat is put away), always, or never.",
                label='When it speaks', heading='Speaking', essential=80)
settings.items('voice_voices', [], scope='global', exclusive='=', check=_check_voices,
               help="A browser voice for a mascot character, as character=voice name; each has its own by default.",
               details='The voice is the name of one of your browser\'s voices. A character not named speaks with a '
                       'voice chosen for it, at its own pitch and pace. An engine a module brings has its own voices.',
               label='Browser voice for each character', heading='Speaking')
settings.boolean('voice_wake', False, scope='global',
                 help="Listen hands-free for the wake phrase; what follows it goes to your system agent.",
                 details='On, the page keeps the microphone open and shows that it listens. Each pause-bounded stretch '
                         'of speech has only its first seconds heard, on this device, for the phrase; nothing else is '
                         'kept or sent. Only what follows the phrase is transcribed and sent to your system agent. '
                         'It needs a local engine: server or browser. Ctrl+Shift+Space turns it on and off.',
                 label='Listen for the wake phrase', heading='Listening')
settings.text('voice_wake_phrase', '', scope='global',
              help="The wake phrase; empty is your mascot's name.",
              label='Wake phrase', heading='Listening')


def language(ctx: Context) -> str | None:
    chosen = str(ctx.nouns.get('language') or ctx.setting('voice_language') or 'auto')
    return None if chosen == 'auto' else chosen


def resolved(ctx: Context) -> tuple[str, str]:
    """The engine in use, and why, in words the page shows beside the mic."""
    chosen = str(ctx.setting('voice_engine'))
    found = engine.machine()
    if chosen == 'off':
        return 'off', 'voice_engine is off.'
    if chosen == 'auto':
        if found['capable']:
            return 'server', f'auto: {found["reason"]}, on this machine.'
        return 'browser', f'auto: Whisper runs in your browser, since {found["reason"]}.'
    if chosen == 'server' and not found['installed']:
        return 'server', f'server is chosen, but the voice extra is not installed: {engine.INSTALL}.'
    if chosen == 'endpoint':
        url = str(ctx.setting('voice_endpoint_url') or '')
        if not url:
            return 'endpoint', 'endpoint is chosen, but voice_endpoint_url is empty.'
        return 'endpoint', f'endpoint: your audio is sent to {urlsplit(url).netloc}.'
    if chosen == 'browser-speech':
        return chosen, "browser-speech: your audio is sent to your browser's vendor."
    brought = engines(ctx.folder).get(chosen)
    if brought is not None:
        why = brought.ready(ctx) if brought.ready else None
        return chosen, f'{chosen} is chosen, but {why}' if why else f'{chosen}: {brought.sends or brought.summary}'
    if chosen not in OWN:
        return 'off', f'{chosen} is chosen, but no enabled module brings it: metaform enable {chosen}.'
    return chosen, f'{chosen} is chosen in voice_engine.'


def _server_model(ctx: Context) -> models.Model:
    return models.SERVER[engine.model_name(str(ctx.nouns.get('model') or ctx.setting('voice_model')),
                                           str(ctx.setting('voice_device')))]


def _browser_model(ctx: Context) -> str:
    chosen = str(ctx.nouns.get('model') or ctx.setting('voice_browser_model'))
    return 'base' if chosen == 'auto' else chosen


def status(ctx: Context) -> dict[str, Any]:
    used, why = resolved(ctx)
    found = engine.machine()
    model = _server_model(ctx)
    where, compute = engine.device(str(ctx.setting('voice_device')))
    browser = _browser_model(ctx)
    url = str(ctx.setting('voice_endpoint_url') or '')
    named = settings.value('web_mascot', ctx.folder) if 'web_mascot' in settings.SCHEMA else None
    mascot = str(named) if named and named != 'none' else None
    return {
        'engine': used, 'chosen': ctx.setting('voice_engine'), 'why': why,
        'send': ctx.setting('voice_send'), 'send_audio': ctx.setting('voice_send_audio'),
        'language': ctx.setting('voice_language'), 'max_seconds': ctx.setting('voice_max_seconds'),
        'server': {'installed': found['installed'], 'capable': found['capable'], 'reason': found['reason'],
                   'install': None if found['installed'] and not found.get('cuda_error') else found['install'],
                   'cuda_error': found.get('cuda_error'), 'device': where,
                   'compute_type': compute, 'gpu': found['gpu'], 'cores': found['cores'], 'model': model.name,
                   'size': model.size, 'downloaded': models.present(models.server_folder(model), model),
                   'loaded': engine.loaded(), 'idle_minutes': IDLE_MINUTES,
                   'downloading': models.status_of(f'server:{model.name}') or None},
        'browser': {'model': browser, 'runtime': f'runtime/{models.RUNTIME_VERSION}/',
                    **{variant: {**models.browser_present(browser, variant),
                                 'downloading': models.status_of(f'browser:{browser}:{variant}') or None}
                       for variant in models.VARIANTS}},
        'tts': {'engine': ctx.setting('voice_tts'), 'speak': ctx.setting('voice_speak'),
                'voices': speech.voices(list(ctx.setting('voice_voices') or [])), 'default': speech.DEFAULT,
                'engines': {name: {'sends': one.sends, 'ready': (one.ready(ctx) if one.ready else None) is None,
                                   'why': one.ready(ctx) if one.ready else None}
                            for name, one in engines(ctx.folder).items() if one.speak}},
        'wake': {'on': ctx.setting('voice_wake'), 'phrase': ctx.setting('voice_wake_phrase') or mascot or '',
                 'mascot': mascot},
        'endpoint': {'configured': bool(url), 'host': urlsplit(url).netloc if url else None,
                     'model': ctx.setting('voice_endpoint_model'), 'key': bool(ctx.setting('voice_endpoint_key_env'))},
    }


def list_models(ctx: Context) -> dict[str, Any]:
    return {'server': [{'model': one.name, 'size': one.size, 'note': one.note, 'repo': one.repo,
                        'downloaded': models.present(models.server_folder(one), one)} for one in models.SERVER.values()],
            'browser': [{'model': name, 'variant': variant, 'size': one.size + models.RUNTIME_SIZE, 'repo': one.repo,
                         'downloaded': models.browser_present(name, variant)['present']}
                        for (name, variant), one in models.BROWSER.items()],
            'folder': str(models.root()), 'browser_folder': str(models.browser_folder())}


def progress(ctx: Context, key: str) -> Callable[[dict[str, Any]], None]:
    """What a download has fetched, published as `voice.download` each time a whole percent more has arrived, so a
    page shows its bar as the bytes come, never by asking."""
    shown = [-1]

    def said(status: dict[str, Any]) -> None:
        total = int(status.get('total') or 0)
        percent = 100 * int(status.get('done') or 0) // total if total else 0
        if percent != shown[0]:
            shown[0] = percent
            ctx.publish('voice.download', {'key': key, **status})
    return said


def download(ctx: Context) -> dict[str, Any]:
    """Fetch a model into the Metaform home once; the page asks the person, showing the size, before it calls this."""
    which = str(ctx.nouns.get('engine') or 'server')
    if which == 'server':
        model = _server_model(ctx)
        key = f'server:{model.name}'
        done = models.download(key, models.server_jobs(model), progress(ctx, key))
        present = models.present(models.server_folder(model), model)
        name, size = model.name, model.size
    elif which == 'browser':
        name, variant = _browser_model(ctx), str(ctx.nouns.get('variant') or 'wasm')
        if (name, variant) not in models.BROWSER:
            raise Stop(f'No browser model {name} for {variant}.', 'metaform voice models')
        key = f'browser:{name}:{variant}'
        done = models.download(key, models.browser_jobs(name, variant), progress(ctx, key))
        present = models.browser_present(name, variant)['present']
        size = models.browser_present(name, variant)['size']
    else:
        raise Stop(f'{which} downloads no model: the engines with models are server and browser.',
                   'metaform voice download engine=server')
    if not present:
        raise Stop(f'The {name} model did not download: {done.get("error") or "it is incomplete"}.',
                   f'metaform voice download engine={which} model={name} --confirm')
    return {'engine': which, 'model': name, 'size': size, 'folder': str(models.root()), 'downloaded': True}


def transcribe(ctx: Context) -> dict[str, Any]:
    """The text of an audio file, with the server engine, or with the person's endpoint when that is their engine."""
    path = Path(str(ctx.nouns['file'])).expanduser()
    if not path.is_file():
        raise Stop(f'No audio file at {path}.', 'metaform voice transcribe <file.wav>')
    chosen = str(ctx.nouns.get('engine') or '')
    if not chosen:
        used, _ = resolved(ctx)
        chosen = 'server' if used in ('auto', 'browser', 'browser-speech', 'off') else used
    limit = int(ctx.setting('voice_max_seconds'))
    brought = engines(ctx.folder).get(chosen)
    if brought is not None and brought.transcribe is not None:
        if ctx.nouns.get('partial'):  # finals only: a service is paid for each pass and hears it once
            return {'text': None, 'busy': True, 'partial': True, 'engine': chosen}
        return {**brought.transcribe(ctx, path, language(ctx)), 'engine': chosen}
    if chosen == 'endpoint':
        url = str(ctx.setting('voice_endpoint_url') or '')
        if not url:
            raise Stop('No transcription endpoint is set.', 'metaform set --voice-endpoint-url <url>')
        if path.stat().st_size > limit * 32000 + 65536 and path.suffix.lower() == '.wav':
            raise Stop(f'The audio is longer than voice_max_seconds, {limit} s.', f'metaform set --voice-max-seconds {limit * 2}')
        try:
            return relay.transcribe(path, url=url, model=str(ctx.setting('voice_endpoint_model')),
                                    key_env=str(ctx.setting('voice_endpoint_key_env') or ''), language=language(ctx))
        except OSError as error:
            raise Stop(str(error), 'metaform config --show voice') from None
    if chosen != 'server':
        raise Stop(f'{chosen} transcribes in the page, not here: the engines here are server and endpoint.',
                   'metaform voice transcribe <file> engine=server')
    if not engine.installed():
        raise Stop('The server engine needs the voice extra, which is not installed.', engine.INSTALL)
    model = _server_model(ctx)
    if not models.present(models.server_folder(model), model):
        raise Stop(f'The {model.name} model is not downloaded yet ({model.size / 1e6:,.0f} MB).',
                   f'metaform voice download model={model.name} --confirm')
    try:
        heard = engine.transcribe(path, name=model.name, language=language(ctx), partial=bool(ctx.nouns.get('partial')),
                                  idle_minutes=IDLE_MINUTES,
                                  prefer=str(ctx.setting('voice_device')))
    except engine.Busy:
        return {'text': None, 'busy': True, 'partial': True, 'engine': 'server'}
    except Exception as error:  # noqa: BLE001  undecodable audio or a model that will not load, said with its cause
        raise Stop(f'Whisper could not hear that audio: {error}', 'metaform voice status') from None
    if heard['seconds'] > limit:
        raise Stop(f'The audio is {heard["seconds"]:.0f} s, longer than voice_max_seconds, {limit} s.',
                   f'metaform set --voice-max-seconds {limit * 2}')
    return heard


def takes_voice(speak_of: Any) -> bool:
    """Whether an engine's speak takes `voice`, a voice id of its own; an engine written before it does not."""
    try:
        parameters = inspect.signature(speak_of).parameters.values()
    except (TypeError, ValueError):
        return False
    return any(one.name == 'voice' or one.kind is inspect.Parameter.VAR_KEYWORD for one in parameters)


def speak(ctx: Context) -> dict[str, Any]:
    """The agent's words spoken by the engine in voice_tts that a module brings: streamed to the page from the web
    GUI, or written to a file from the command line. The browser's own voices speak in the page and need nothing here."""
    given: Any = ctx.nouns['text']
    text = ' '.join(str(word) for word in cast(list[Any], given)) if isinstance(given, (list, tuple)) else str(given)
    name = str(ctx.nouns.get('engine') or ctx.setting('voice_tts'))
    brought = engines(ctx.folder).get(name)
    if brought is None or brought.speak is None:
        raise Stop(f'{name} speaks in the page, or is not an engine an enabled module brings.', 'metaform voice status')
    output = str(ctx.nouns.get('format') or 'page')
    character = str(ctx.nouns.get('character') or '') or None
    voice = str(ctx.nouns.get('voice') or '') or None
    if voice and takes_voice(brought.speak):
        audio = brought.speak(ctx, text, character, output, voice=voice)
    else:  # an engine that takes no voice id speaks with the character's voice
        audio = brought.speak(ctx, text, character, output)
    concrete = brought.output(ctx, output) if brought.output else output
    if ctx.surface == 'web':
        return {'stream': audio, 'engine': name, 'format': concrete}
    target = Path(str(ctx.nouns.get('file') or 'speech.audio')).expanduser()
    if home.is_home_path(target):
        home.mkdir_private(target.parent)
        home.write_private(target, b'')
    with target.open('wb') as out:
        for chunk in audio:
            out.write(chunk)
    return {'file': str(target), 'bytes': target.stat().st_size, 'engine': name}


# Minutes the server keeps its Whisper model loaded after the person last spoke: long enough that a conversation never
# waits on a reload, short enough that an idle machine gets its memory back. Settings cleanup 2026-10-15 made it fixed.
IDLE_MINUTES = 10
# The language settings merged into voice_language, settings cleanup 2026-10-15, the phone's first: each was the
# language the person speaks.
MERGED_LANGUAGES = (('twilio', 'twilio_language'), ('elevenlabs', 'elevenlabs_scribe_language'))


def carry_language(ctx: Context | None = None) -> list[str]:
    """Once per home, as voice starts: a language stored in twilio_language or elevenlabs_scribe_language becomes
    voice_language when the person has not set that, and the old rows are removed. All three were global."""
    del ctx
    return settings.carry_once('speech-language', _carry_language)


def _carry_language() -> list[str]:
    said: list[str] = []
    found = [(owner, key, (home.stored('global', owner, key) or [None])[0]) for owner, key in MERGED_LANGUAGES]
    chosen = next((str(value) for _, _, value in found if value not in (None, 'auto')), None)
    if chosen is not None and home.stored('global', 'voice', 'voice_language') is None:
        home.save('global', 'voice', 'voice_language', [chosen])
        said.append(f'voice_language = {chosen}')
    for owner, key, value in found:
        if value is not None or home.glued('global', owner, key):
            home.clear('global', owner, key)
            home.set_glue('global', owner, key, False)
            said.append(f'{key} ({value}) removed')
    return said


MODULE = Module(
    id='voice',
    summary='Speech to text: talk to Metaform instead of typing, with Whisper on your own machine.',
    purpose='Turns what a person says into text in the box they speak into on the web GUI, with Whisper running on '
            'this machine or in their browser, so their audio stays on their own devices unless they choose a service '
            'that says it sends it. Details: metaform help voice.',
    details='The page holds the mic and push-to-talk; these commands show which engine hears and why, list and '
            'download the models, and transcribe an audio file with the server engine.',
    verbs=(
        Verb('status', status, 'Show which speech engine is in use and why, its device, model and whether it is loaded.',
             effect='read', surfaces=('cli',)),
        Verb('models', list_models, "List each engine's Whisper models, their sizes and whether they are downloaded.",
             effect='read', surfaces=('cli',)),
        Verb('transcribe', transcribe, "Turn an audio file's speech into text, with its segments.",
             nouns=(Noun('file', 'The audio file: wav, flac, mp3, ogg or webm.'),
                    Noun('language', 'The language spoken, such as en; auto by default.', required=False),
                    Noun('partial', 'A quick pass of an utterance still being spoken.', kind='bool', required=False),
                    Noun('engine', 'server, elevenlabs or endpoint; the engine in use by default.', required=False),
                    Noun('model', 'The server model; voice_model by default.', required=False)),
             examples=(('metaform voice transcribe ~/clip.wav', 'Prints its text with the server engine.'),),
             effect='read', open_world=True, task=True, surfaces=('cli',)),
        Verb('download', download, 'Download a Whisper model once into the Metaform home, showing its size first.',
             nouns=(Noun('engine', 'server or browser; server by default.', required=False),
                    Noun('model', 'The model; the engine\'s setting by default.', required=False),
                    Noun('variant', 'For the browser: wasm or webgpu.', required=False)),
             caution='This downloads a Whisper model, 40 MB to 1.6 GB, from Hugging Face into the Metaform home.',
             effect='write', open_world=True, task=True, surfaces=('cli',)),
        Verb('speak', speak, 'Speak text into an audio file with the voice_tts engine a module brings.',
             nouns=(Noun('character', 'The mascot character whose voice speaks it.', required=False),
                    Noun('voice', "A voice id of the engine's own, in place of the character's voice.", required=False),
                    Noun('engine', 'The engine; voice_tts by default.', required=False),
                    Noun('format', "page, phone, or one of the engine's own formats; page by default.", required=False),
                    Noun('file', 'The file to write; speech.audio by default.', required=False),
                    Noun('text', 'What to say.', many=True)),
             examples=(('metaform voice speak character=owl -- "Hello there."', "Writes speech.audio in the owl's voice."),),
             surfaces=('cli',), effect='write', open_world=True),  # not an agent's to spend the person's account on
    ),
    subscriptions=(),
    start=carry_language,
    stop=lambda ctx: engine.unload(),
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
    provides=(Provides('voice', service.VOICE),),
    settings_category='voice',
)
