"""voice: the engine chosen and said, the server engine refused with its next step, and every network call mocked:
no model is loaded, no microphone is opened, and nothing reaches ElevenLabs or an endpoint."""
from __future__ import annotations

import importlib
import io
import json
import math
import sys
import urllib.request

import pytest

pytestmark = pytest.mark.kind('fixture')
FAKE_KEY = 'test-key-not-real'


@pytest.fixture
def voice(run, monkeypatch):
    """The voice module as the loader loaded it, the copy its commands run, each part by name: voice('engine')."""
    monkeypatch.delenv('ELEVENLABS_API_KEY', raising=False)
    run('voice', 'models')

    package = next(key for key in sys.modules if key.startswith('metaform_module_') and key.endswith('_voice'))
    assert package

    def part(name):
        return importlib.import_module(f'{package}.{name}')
    part('engine')._probe.clear()
    yield part
    part('engine')._probe.clear()
    part('engine').unload()


class Answer(io.BytesIO):
    """A stand-in for urlopen's answer, readable in chunks and usable as a context manager."""
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def caught(monkeypatch, body: bytes):
    """Every urlopen call recorded and answered with `body`; nothing goes out."""
    calls = []

    def urlopen(request, timeout=None):
        calls.append(request)
        return Answer(body)
    monkeypatch.setattr(urllib.request, 'urlopen', urlopen)
    return calls


def test_auto_runs_whisper_in_the_browser_where_the_extra_is_not_installed_and_says_how_to_install(run, voice, monkeypatch):
    monkeypatch.setattr(voice('engine'), 'installed', lambda: False)
    found = json.loads(run('voice', 'status', '--json').stdout)
    assert found['engine'] == 'browser' and 'not installed' in found['why']
    assert 'metaform[voice]' in found['server']['install'] and found['server']['capable'] is False
    refused = run('voice', 'transcribe', __file__, 'engine=server', ok=False)
    assert 'voice extra' in refused.stderr and 'metaform[voice]' in refused.stderr


def test_auto_chooses_the_server_on_a_gpu_and_the_transcript_comes_from_the_loaded_model(run, voice, monkeypatch, home, tmp_path):
    engine, models = voice('engine'), voice('models')
    monkeypatch.setattr(engine, 'installed', lambda: True)
    engine._probe.update(installed=True, cuda=1, gpu='Test GPU', cores=4, capable=True, install=engine.INSTALL,
                         reason='an NVIDIA GPU (Test GPU) runs Whisper here')
    monkeypatch.setattr(models, 'present', lambda folder, model: True)
    seen = {}

    def transcribe(path, **given):
        seen.update(given, path=path)
        return {'text': 'ask not', 'segments': [], 'seconds': 1.0, 'partial': given['partial']}
    monkeypatch.setattr(engine, 'transcribe', transcribe)
    clip = tmp_path / 'clip.wav'
    clip.write_bytes(b'RIFF')
    found = json.loads(run('voice', 'status', '--json').stdout)
    assert found['engine'] == 'server' and found['server']['model'] == 'large-v3-turbo'
    heard = json.loads(run('voice', 'transcribe', str(clip), 'partial=true', '--json').stdout)
    assert heard['text'] == 'ask not' and seen['partial'] is True and seen['name'] == 'large-v3-turbo'


def test_a_gpu_whose_cublas_does_not_load_runs_on_the_cpu_and_status_says_why_with_the_install(run, voice, monkeypatch):
    engine = voice('engine')
    monkeypatch.setattr(engine, 'installed', lambda: True)
    monkeypatch.setitem(sys.modules, 'ctranslate2', type(sys)('ctranslate2'))
    sys.modules['ctranslate2'].get_cuda_device_count = lambda: 1
    monkeypatch.setattr(engine, '_gpu_name', lambda: 'Test GPU')
    monkeypatch.setattr(engine, '_cuda_libraries', lambda: None)
    monkeypatch.setattr(engine, 'CUBLAS', 'libcublas-not-here.so.12')
    monkeypatch.setattr(engine.os, 'cpu_count', lambda: 16)
    found = json.loads(run('voice', 'status', '--json').stdout)
    assert found['engine'] == 'server' and found['server']['device'] == 'cpu' and found['server']['model'] == 'small'
    assert 'libcublas-not-here.so.12' in found['server']['reason']
    assert 'voice-gpu' in found['server']['install'] and found['server']['cuda_error']
    assert engine.device('cuda') == ('cpu', 'int8')


def test_a_partial_asked_while_another_runs_is_answered_busy_and_never_queued(voice, tmp_path):
    engine = voice('engine')
    engine._lock.acquire()
    try:
        with pytest.raises(engine.Busy):
            engine.transcribe(tmp_path / 'x.wav', name='tiny', language=None, partial=True, idle_minutes=0)
    finally:
        engine._lock.release()


def test_the_endpoint_receives_the_audio_and_the_key_named_by_the_setting_and_nothing_else(run, voice, monkeypatch, tmp_path):
    calls = caught(monkeypatch, b'{"text": "hello there"}')
    monkeypatch.setenv('MY_STT_KEY', FAKE_KEY)
    run('set', '--voice-engine', 'endpoint', '--voice-endpoint-url', 'http://127.0.0.1:9/v1/audio/transcriptions',
        '--voice-endpoint-key-env', 'MY_STT_KEY')
    clip = tmp_path / 'clip.wav'
    clip.write_bytes(b'RIFFaudio')
    heard = json.loads(run('voice', 'transcribe', str(clip), '--json').stdout)
    assert heard == {**heard, 'text': 'hello there', 'engine': 'endpoint'}
    [sent] = calls
    assert sent.full_url == 'http://127.0.0.1:9/v1/audio/transcriptions'
    assert sent.get_header('Authorization') == f'Bearer {FAKE_KEY}' and b'RIFFaudio' in sent.data
    assert b'name="model"\r\n\r\nwhisper-1' in sent.data


def test_a_phone_stream_in_mu_law_yields_a_final_text_for_each_utterance_and_skips_silence(voice, monkeypatch, tmp_path):
    from metaform.module import provided
    [(owner, service)] = provided(tmp_path, 'voice')  # what a phone bridge finds, never importing voice
    assert owner == 'voice'
    ulaw = voice('service').ULAW
    assert ulaw[0xFF] == 0 and ulaw[0x00] == -32124 and ulaw[0x80] == 32124
    heard = []

    def hear(self, folder, samples, rate, **given):
        heard.append((len(samples) / rate, given['partial']))
        return 'hello'
    monkeypatch.setattr(type(service), '_hear', hear)
    encode = {value: byte for byte, value in reversed(list(enumerate(ulaw)))}
    loud = bytes(encode[min(ulaw, key=lambda v: abs(v - int(8000 * math.sin(i / 3))))] for i in range(160))
    quiet = bytes([0xFF]) * 160  # 20 ms frames, as a call sends them
    call = [quiet] * 25 + [loud] * 50 + [quiet] * 60
    found = list(service.transcribe_stream(tmp_path, call, format='ulaw_8000'))
    assert found[-1] == {'text': 'hello', 'final': True}
    finals = [one for one in heard if not one[1]]
    assert len(finals) == 1 and 1.0 <= finals[0][0] <= 2.0  # the speech and its pause, never the silence before


@pytest.mark.req('CLI-011')
def test_the_phone_and_scribe_languages_carry_once_into_voice_language(voice):
    """Settings cleanup 2026-10-15: twilio_language and elevenlabs_scribe_language merge into voice_language, the one
    language the person is heard in; a stored value carries there once, the phone's first, and the old rows go."""
    from metaform import home, settings
    home.save('global', 'twilio', 'twilio_language', ['de'])
    home.save('global', 'elevenlabs', 'elevenlabs_scribe_language', ['fr'])
    with home.chassis(write=True) as db:  # the test home's own start carried nothing and marked it; undo the mark
        db.execute("DELETE FROM meta WHERE key='carried:speech-language'")
    settings._carried.clear()
    module = sys.modules[voice('engine').__package__]
    said = module.carry_language()
    assert said[0] == 'voice_language = de' and settings.value('voice_language', home.home()) == 'de'
    assert home.stored('global', 'twilio', 'twilio_language') is None
    assert home.stored('global', 'elevenlabs', 'elevenlabs_scribe_language') is None
    assert module.carry_language() == [], 'once per home'


def test_a_model_download_is_kept_only_whole(voice, monkeypatch, home):
    models = voice('models')
    caught(monkeypatch, b'x' * 10)
    jobs = [('https://example.invalid/a', models.root() / 'test' / 'a.bin', 10, None),
            ('https://example.invalid/b', models.root() / 'test' / 'b.bin', 11, None)]
    done = models.download('test', jobs)
    assert done['state'] == 'failed' and '10 bytes, not 11' in done['error']
    assert (models.root() / 'test' / 'a.bin').is_file() and not list((models.root() / 'test').glob('*.part'))
    assert not (models.root() / 'test' / 'b.bin').exists()
