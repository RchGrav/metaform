"""elevenlabs: an engine the voice module finds by `provides`, with every HTTP call mocked and a key that is not real.
Nothing reaches ElevenLabs, no real key is read, and no microphone is opened."""
from __future__ import annotations

import importlib
import io
import json
import sys
import urllib.error
import urllib.request

import pytest

pytestmark = pytest.mark.kind('fixture')
FAKE_KEY = 'test-key-not-real'


@pytest.fixture
def eleven(run, monkeypatch):
    """The elevenlabs module as the loader loaded it, the copy its engine runs: eleven('api')."""
    monkeypatch.delenv('ELEVENLABS_API_KEY', raising=False)
    run('elevenlabs', 'status')
    package = next(key for key in sys.modules if key.startswith('metaform_module_') and key.endswith('_elevenlabs'))
    importlib.import_module(f'{package}.api')._cache.clear()
    return lambda name: importlib.import_module(f'{package}.{name}')


class Answer(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def caught(monkeypatch, *bodies: bytes):
    """Every urlopen call recorded and answered in turn; nothing goes out."""
    calls = []

    def urlopen(request, timeout=None):
        calls.append(request)
        return Answer(bodies[min(len(calls), len(bodies)) - 1])
    monkeypatch.setattr(urllib.request, 'urlopen', urlopen)
    return calls


def test_voice_finds_the_engine_and_a_phone_call_hears_it_in_mu_law_with_the_settings_in_the_request(
        run, eleven, monkeypatch, tmp_path):
    from metaform.module import provided
    monkeypatch.setenv('ELEVENLABS_API_KEY', FAKE_KEY)
    calls = caught(monkeypatch, b'\xff' * 10000)
    run('set', '--voice-tts', 'elevenlabs', '--elevenlabs-stability', '30', '--elevenlabs-speed', '110',
        '--no-elevenlabs-speaker-boost')
    assert [name for _, name in [(one, engine.name) for one, engine in provided(tmp_path, 'voice.engine')]] == ['elevenlabs']
    [(_, voice)] = provided(tmp_path, 'voice')
    chunks = list(voice.speak(tmp_path, 'Hello, caller.', format='phone', character='owl'))
    assert b''.join(chunks) == b'\xff' * 10000 and len(chunks) > 1  # streamed, chunk by chunk
    [sent] = calls
    assert sent.full_url.startswith(f'{eleven("api").API}/text-to-speech/onwK4e9ZLuTAKqWW03F9/stream?')
    assert 'output_format=ulaw_8000' in sent.full_url and sent.get_header('Xi-api-key') == FAKE_KEY
    body = json.loads(sent.data)
    assert body['text'] == 'Hello, caller.' and body['model_id'] == 'eleven_flash_v2_5'
    assert body['voice_settings'] == {'stability': 0.3, 'similarity_boost': 0.75, 'style': 0.0,
                                      'use_speaker_boost': False, 'speed': 1.1}


def test_a_voice_the_caller_names_speaks_in_place_of_the_characters(run, eleven, monkeypatch, tmp_path):
    """The voice service's `voice`, as the twilio module passes twilio_voice, reaches ElevenLabs as the voice id."""
    from metaform.module import provided
    monkeypatch.setenv('ELEVENLABS_API_KEY', FAKE_KEY)
    calls = caught(monkeypatch, b'\xff' * 100)
    run('set', '--voice-tts', 'elevenlabs')
    [(_, voice)] = provided(tmp_path, 'voice')
    list(voice.speak(tmp_path, 'Hello.', format='phone', character='owl', voice='ChosenVoiceId0000000'))
    list(voice.speak(tmp_path, 'Hello.', format='phone', character='owl'))
    assert [sent.full_url.split('/stream?')[0].rsplit('/', 1)[1] for sent in calls] == ['ChosenVoiceId0000000',
                                                                                         'onwK4e9ZLuTAKqWW03F9']


def test_general_voice_serves_every_unoverridden_character_and_caller_still_wins(run, eleven, monkeypatch, tmp_path):
    from metaform.module import provided
    monkeypatch.setenv('ELEVENLABS_API_KEY', FAKE_KEY)
    calls = caught(monkeypatch, b'audio')
    run('set', '--elevenlabs-voice', 'GeneralVoiceId000000', '--elevenlabs-voices', 'owl=OverrideVoiceId0000')
    # Choosing a voice alone never selects a paid engine or synthesizes anything.
    from metaform import settings
    assert settings.value('voice_tts', tmp_path) == 'browser'
    assert calls == []
    [(_, voice)] = provided(tmp_path, 'voice')
    provider = importlib.import_module(eleven('api').__package__)
    characters = [*provider.DEFAULT_VOICES, 'unknown', None]
    for character in characters:
        list(voice.speak(tmp_path, 'Hello.', engine='elevenlabs', character=character))
    list(voice.speak(tmp_path, 'Hello.', engine='elevenlabs', character='owl', voice='CallerVoiceId0000000'))
    assert [sent.full_url.split('/stream?')[0].rsplit('/', 1)[1] for sent in calls] == [
        *['OverrideVoiceId0000' if character == 'owl' else 'GeneralVoiceId000000' for character in characters],
        'CallerVoiceId0000000']
    run('unset', '--elevenlabs-voice')
    list(voice.speak(tmp_path, 'Hello.', engine='elevenlabs', character='beetle'))
    list(voice.speak(tmp_path, 'Hello.', engine='elevenlabs', character='owl'))
    assert [sent.full_url.split('/stream?')[0].rsplit('/', 1)[1] for sent in calls[-2:]] == [
        provider.DEFAULT_VOICES['beetle'], 'OverrideVoiceId0000']


def test_general_voice_name_resolves_through_account_and_listing_shows_effective_voices(
        run, eleven, monkeypatch, tmp_path):
    from metaform.module import context
    monkeypatch.setenv('ELEVENLABS_API_KEY', FAKE_KEY)
    calls = caught(monkeypatch, b'{"voices": [{"voice_id": "abcdefghijklmnopqrst", "name": "Daniel"}]}', b'audio')
    run('set', '--elevenlabs-voice', 'Daniel', '--elevenlabs-voices', 'owl=OverrideVoiceId0000')
    listed = json.loads(run('elevenlabs', 'voices', '--json').stdout)
    assert listed['default'] == 'Daniel'
    assert listed['characters']['owl'] == 'OverrideVoiceId0000'
    assert listed['characters']['beetle'] == 'Daniel'
    provider = importlib.import_module(eleven('api').__package__)
    assert provider.voice_of(context('elevenlabs', tmp_path), 'beetle') == 'abcdefghijklmnopqrst'
    assert len(calls) == 1  # only the account listing, never synthesis


def test_without_its_key_it_refuses_and_a_refusal_never_carries_the_key(run, eleven, monkeypatch):
    refused = run('elevenlabs', 'speak', '--', 'hello', ok=False)
    assert 'ELEVENLABS_API_KEY' in refused.stderr
    assert json.loads(run('elevenlabs', 'status', '--json').stdout)['key'] is False
    monkeypatch.setenv('ELEVENLABS_API_KEY', FAKE_KEY)

    def urlopen(request, timeout=None):
        raise urllib.error.HTTPError(request.full_url, 401, 'no', {}, io.BytesIO(b'{"detail": "invalid key"}'))
    monkeypatch.setattr(urllib.request, 'urlopen', urlopen)
    with pytest.raises(OSError) as error:
        eleven('api').tts('hi', 'onwK4e9ZLuTAKqWW03F9')
    assert '401' in str(error.value) and FAKE_KEY not in str(error.value)


def test_scribe_hears_a_file_when_elevenlabs_is_the_voice_engine(run, eleven, monkeypatch, tmp_path):
    monkeypatch.setenv('ELEVENLABS_API_KEY', FAKE_KEY)
    calls = caught(monkeypatch, b'{"text": "ask what you can do", "language_code": "en"}')
    run('set', '--voice-engine', 'elevenlabs', '--voice-language', 'en')
    clip = tmp_path / 'clip.wav'
    clip.write_bytes(b'RIFF')
    heard = json.loads(run('voice', 'transcribe', str(clip), '--json').stdout)
    assert heard['text'] == 'ask what you can do' and heard['engine'] == 'elevenlabs'
    assert calls[0].full_url.endswith('/speech-to-text') and b'scribe_v1' in calls[0].data
    assert b'name="language_code"\r\n\r\nen' in calls[0].data


def test_the_models_come_from_the_account_and_a_voice_is_named_by_its_name(run, eleven, monkeypatch, tmp_path,
                                                                           project_folder):
    """The account's models are the choices once metaform elevenlabs models has listed them."""
    monkeypatch.setenv('ELEVENLABS_API_KEY', FAKE_KEY)
    caught(monkeypatch, json.dumps([{'model_id': 'eleven_flash_v2_5', 'name': 'Flash', 'can_do_text_to_speech': True},
                                    {'model_id': 'eleven_v4', 'name': 'v4', 'can_do_text_to_speech': True}]).encode(),
           json.dumps({'voices': [{'voice_id': 'abcdefghijklmnopqrst', 'name': 'Daniel'}]}).encode(), b'audio')
    assert run('set', '--elevenlabs-model', 'eleven_v4', cwd=project_folder, ok=False).returncode != 0
    run('elevenlabs', 'models', cwd=project_folder)
    assert run('set', '--elevenlabs-model', 'eleven_v4', cwd=project_folder).returncode == 0
    assert run('set', '--elevenlabs-model', 'eleven_v3', cwd=project_folder, ok=False).returncode != 0
    assert run('set', '--elevenlabs-model', 'eleven_v4', cwd=tmp_path).returncode == 0  # a global setting's choices
    run('set', '--elevenlabs-voices', 'owl=Daniel', cwd=project_folder)
    run('elevenlabs', 'speak', 'character=owl', f'file={tmp_path / "x.pcm"}', '--', 'hi', cwd=project_folder)
    assert (tmp_path / 'x.pcm').read_bytes() == b'audio'


def test_voice_named_asks_again_after_elevenlabs_failed_once(eleven, monkeypatch):
    """A failed listing is not kept: the next speak with a named voice asks ElevenLabs again."""
    monkeypatch.setenv('ELEVENLABS_API_KEY', FAKE_KEY)
    calls = []

    def urlopen(request, timeout=None):
        calls.append(request.full_url)
        if len(calls) == 1:
            raise urllib.error.URLError('blip')
        return Answer(json.dumps({'voices': [{'voice_id': 'abcdefghijklmnopqrst', 'name': 'Daniel'}]}).encode())
    monkeypatch.setattr(urllib.request, 'urlopen', urlopen)
    with pytest.raises(OSError):
        eleven('api').voice_named('Daniel')
    assert eleven('api').voice_named('Daniel') == 'abcdefghijklmnopqrst' and len(calls) == 2


def test_disabling_the_module_withdraws_the_engine_from_voice(run, eleven, tmp_path):
    from metaform.module import provided
    assert provided(tmp_path, 'voice.engine')
    run('disable', 'elevenlabs')
    assert provided(tmp_path, 'voice.engine') == []
    assert run('set', '--voice-tts', 'elevenlabs', ok=False).returncode != 0
    assert 'elevenlabs' not in json.loads(run('voice', 'status', '--json').stdout)['tts']['engines']
