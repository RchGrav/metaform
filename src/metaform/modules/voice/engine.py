"""The server engine: faster-whisper on this machine, kept loaded in the process that serves the page.

faster-whisper is an optional extra, so nothing here imports it until a transcription or a status asks. On NVIDIA
hardware it runs on CUDA in float16, with the cuBLAS and cuDNN libraries of the `voice-gpu` extra loaded from their
wheels; otherwise on the CPU in int8. A loaded model stays in memory between utterances and is let go after the idle
time the person set, so a page left open does not hold a gigabyte of GPU memory for nothing.
"""
from __future__ import annotations

import ctypes
import importlib.util
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

from . import models

INSTALL = ("pip install 'metaform[voice]', or 'metaform[voice-gpu]' with an NVIDIA GPU; "
           'from a source checkout, uv sync --extra voice (or --extra voice-gpu)')
STRONG_CPU = 8  # cores from which the server's CPU engine beats the page's WebAssembly one at a usable model size

_lock = threading.Lock()  # one transcription at a time: a GPU serves one well, two badly
_state: dict[str, Any] = {'model': None, 'key': None, 'used': 0.0, 'timer': None, 'loads': 0}
_probe: dict[str, Any] = {}


def installed() -> bool:
    return importlib.util.find_spec('faster_whisper') is not None and importlib.util.find_spec('ctranslate2') is not None


def _cuda_libraries() -> None:
    """Load the CUDA libraries of the nvidia-* wheels into the process, so CTranslate2 finds them without a library
    path set before the process started. A wheel that is not there is no error: CUDA is then not offered."""
    spec = importlib.util.find_spec('nvidia')
    if spec is None or not spec.submodule_search_locations:
        return
    base = Path(next(iter(spec.submodule_search_locations)))
    names = (('cublas', ('libcublasLt.so.12', 'libcublas.so.12')),
             ('cudnn', ('libcudnn.so.9', 'libcudnn_ops.so.9', 'libcudnn_cnn.so.9', 'libcudnn_adv.so.9',
                        'libcudnn_graph.so.9', 'libcudnn_engines_runtime_compiled.so.9',
                        'libcudnn_engines_precompiled.so.9', 'libcudnn_heuristic.so.9')))
    if sys.platform == 'win32':
        for package, _ in names:
            folder = base / package / 'bin'
            if folder.is_dir():
                os.add_dll_directory(str(folder))
        return
    for package, files in names:
        for name in files:
            path = base / package / 'lib' / name
            if path.is_file():
                try:
                    ctypes.CDLL(str(path), mode=ctypes.RTLD_GLOBAL)
                except OSError:
                    pass


def machine() -> dict[str, Any]:
    """What this machine offers the server engine, found once per process: the extra, a CUDA device, the CPU cores,
    and whether it serves speech well enough to be chosen over the page's own engine, with the reason in words."""
    if _probe:
        return dict(_probe)
    cores = os.cpu_count() or 1
    found: dict[str, Any] = {'installed': installed(), 'install': INSTALL, 'cores': cores, 'cuda': 0, 'gpu': None}
    if found['installed']:
        try:
            import ctranslate2  # type: ignore[import-not-found]
            found['cuda'] = int(ctranslate2.get_cuda_device_count())  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001  a broken CUDA stack means CPU, never a failure
            found['cuda'] = 0
        if found['cuda']:
            found['gpu'] = _gpu_name()
    if not found['installed']:
        found.update(capable=False, reason='the voice extra is not installed here')
    elif found['cuda']:
        named = f' ({found["gpu"]})' if found['gpu'] else ''
        found.update(capable=True, reason=f'an NVIDIA GPU{named} runs Whisper here')
    elif cores >= STRONG_CPU:
        found.update(capable=True, reason=f'{cores} CPU cores run Whisper here')
    else:
        found.update(capable=False, reason=f'{cores} CPU cores are too few to beat the browser')
    _probe.update(found)
    return dict(found)


def _gpu_name() -> str | None:
    try:
        done = subprocess.run(['nvidia-smi', '--query-gpu=name', '--format=csv,noheader'], capture_output=True,
                              text=True, timeout=5, check=False)
        return done.stdout.strip().splitlines()[0] if done.returncode == 0 and done.stdout.strip() else None
    except (OSError, subprocess.SubprocessError):
        return None


def device(prefer: str = 'auto') -> tuple[str, str]:
    """The device and the compute type: CUDA in float16 where there is one, else the CPU in int8; `prefer`, the
    person's voice_device, holds it to cpu, or to cuda where CUDA is found."""
    cuda = bool(machine()['cuda']) and prefer != 'cpu'
    return ('cuda', 'float16') if cuda else ('cpu', 'int8')


def model_name(chosen: str, prefer: str = 'auto') -> str:
    """auto is large-v3-turbo on a GPU and small on a CPU."""
    if chosen != 'auto':
        return chosen
    return 'large-v3-turbo' if device(prefer)[0] == 'cuda' else 'small'


def loaded() -> str | None:
    return _state['key'][0] if _state['model'] is not None else None


def _load(name: str, prefer: str) -> Any:
    from faster_whisper import WhisperModel  # type: ignore[import-not-found]
    model = models.SERVER[name]
    folder = models.server_folder(model)
    if not models.present(folder, model):
        raise FileNotFoundError(name)
    where, compute = device(prefer)
    if where == 'cuda':
        _cuda_libraries()  # loaded only when a model is, so a page that never speaks costs the server nothing
    key = (name, where, compute)
    if _state['key'] != key or _state['model'] is None:
        unload()
        threads = min(16, max(1, (os.cpu_count() or 2) // 2)) if where == 'cpu' else 0
        _state['model'] = WhisperModel(str(folder), device=where, compute_type=compute, cpu_threads=threads)
        _state['key'] = key
        _state['loads'] += 1
    return _state['model']


def unload() -> None:
    """Let the model go; the next utterance loads it again."""
    timer = _state.get('timer')
    if timer is not None:
        timer.cancel()
    _state.update(model=None, key=None, timer=None)


def _keep(minutes: int) -> None:
    """Let the model go after `minutes` without an utterance; 0 keeps it for as long as the process runs."""
    timer = _state.get('timer')
    if timer is not None:
        timer.cancel()
    _state['timer'] = None
    if minutes > 0:
        def idle() -> None:
            with _lock:
                if time.monotonic() - _state['used'] >= minutes * 60 - 1:
                    unload()
        _state['timer'] = threading.Timer(minutes * 60, idle)
        _state['timer'].daemon = True
        _state['timer'].start()


def decode(path: Path) -> Any:
    """The audio as 16 kHz mono float32 samples, decoded with PyAV, which faster-whisper brings: wav, flac, mp3, ogg
    and the webm/opus a browser's MediaRecorder writes. faster-whisper's own decode_audio passes an argument that
    newer PyAV releases no longer take, so it is done here with the calls every release has."""
    import av  # type: ignore[import-not-found]
    import numpy as numpy_module  # type: ignore[import-not-found]
    numpy: Any = numpy_module
    resampler = av.AudioResampler(format='s16', layout='mono', rate=16000)
    chunks: list[Any] = []
    with av.open(str(path), mode='r') as container:
        for frame in container.decode(audio=0):
            frame.pts = None
            for out in resampler.resample(frame):
                chunks.append(out.to_ndarray().reshape(-1))
        for out in resampler.resample(None):
            chunks.append(out.to_ndarray().reshape(-1))
    if not chunks:
        return numpy.zeros(0, dtype=numpy.float32)
    return numpy.concatenate(chunks).astype(numpy.float32) / 32768.0


class Busy(Exception):
    """A partial asked for while another transcription runs: skipped, since the next partial will carry its words."""


def transcribe(path: Path, *, name: str, language: str | None, partial: bool, idle_minutes: int,
               prefer: str = 'auto') -> dict[str, Any]:
    """The text of one utterance and its segments. A partial is a quick greedy pass of the audio so far, refused at
    once while another transcription runs; a final one waits its turn and searches more widely."""
    if not _lock.acquire(blocking=not partial):
        raise Busy()
    try:
        began = time.perf_counter()
        model = _load(name, prefer)
        loaded_in = time.perf_counter() - began
        audio = decode(path)
        seconds = len(audio) / 16000
        segments, info = model.transcribe(
            audio, language=language, beam_size=1 if partial else 5, best_of=1 if partial else 5,
            temperature=0.0 if partial else [0.0, 0.2, 0.4, 0.6, 0.8, 1.0], condition_on_previous_text=False,
            without_timestamps=partial, vad_filter=not partial)
        parts = [{'start': round(one.start, 2), 'end': round(one.end, 2), 'text': one.text.strip()} for one in segments]
        took = time.perf_counter() - began
        _state['used'] = time.monotonic()
        where, compute = _state['key'][1], _state['key'][2]
        return {'text': ' '.join(part['text'] for part in parts if part['text']).strip(), 'segments': parts,
                'language': info.language, 'seconds': round(seconds, 2), 'took': round(took, 3),
                'loaded_in': round(loaded_in, 3), 'engine': 'server', 'model': name, 'device': where,
                'compute_type': compute, 'partial': partial}
    finally:
        _keep(idle_minutes)
        _lock.release()
