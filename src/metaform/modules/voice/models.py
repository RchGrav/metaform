"""The Whisper models voice can use, and the one place they are downloaded to: the Metaform home's models folder.

Two engines run Whisper on the person's own machine. The server engine, faster-whisper, reads CTranslate2 models;
the page's own engine, transformers.js, reads ONNX models and needs ONNX Runtime's WebAssembly binary. Every file is
named here with its repository, its pinned revision and its size, so the page can say what a download costs before
the person agrees to it, and a download is checked against what was promised. Nothing is fetched until the person
asks, and nothing is written anywhere but `<home>/models`.
"""
from __future__ import annotations

import hashlib
import shutil
import threading
import time
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from metaform import home

HUB = 'https://huggingface.co'
CHUNK = 1 << 20
TIMEOUT = 60


@dataclass(frozen=True)
class Model:
    """One downloadable set of files: a Hugging Face repository at a fixed revision, each file with its size."""
    name: str
    repo: str
    revision: str
    files: tuple[tuple[str, int], ...]
    note: str = ''

    @property
    def size(self) -> int:
        return sum(size for _, size in self.files)


_CT2_TOKENIZER = (('tokenizer.json', 2203239), ('vocabulary.txt', 459861))

# faster-whisper's CTranslate2 conversions, as faster_whisper.utils names them; large-v3-turbo's repository moved from
# mobiuslabsgmbh to dropbox-dash with the same files.
SERVER: dict[str, Model] = {
    'tiny': Model('tiny', 'Systran/faster-whisper-tiny', 'd90ca5fe260221311c53c58e660288d3deb8d356',
                  (('config.json', 2249), ('model.bin', 75538270), *_CT2_TOKENIZER), 'fastest, least accurate'),
    'base': Model('base', 'Systran/faster-whisper-base', 'ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66',
                  (('config.json', 2309), ('model.bin', 145217532), *_CT2_TOKENIZER), 'fast'),
    'small': Model('small', 'Systran/faster-whisper-small', '536b0662742c02347bc0e980a01041f333bce120',
                   (('config.json', 2370), ('model.bin', 483546902), *_CT2_TOKENIZER), 'the CPU default'),
    'medium': Model('medium', 'Systran/faster-whisper-medium', '08e178d48790749d25932bbc082711ddcfdfbc4f',
                    (('config.json', 2257), ('model.bin', 1527906378), *_CT2_TOKENIZER), 'accurate, slow on CPU'),
    'large-v3-turbo': Model('large-v3-turbo', 'dropbox-dash/faster-whisper-large-v3-turbo',
                            '0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf',
                            (('config.json', 2263), ('model.bin', 1617884929), ('preprocessor_config.json', 340),
                             ('tokenizer.json', 2710337), ('vocabulary.json', 1068114)), 'the GPU default'),
}

# The page's engine: onnx-community's ONNX exports, which transformers.js reads. The WebAssembly build runs the 8-bit
# quantized encoder and decoder; WebGPU runs the full-precision encoder and the 4-bit decoder, as transformers.js's own
# Whisper WebGPU example does, since WebGPU has no fast 8-bit kernels.
def _onnx_common(config: int, generation: int, tokenizer_config: int) -> tuple[tuple[str, int], ...]:
    return (('config.json', config), ('generation_config.json', generation), ('preprocessor_config.json', 339),
            ('tokenizer.json', 2480466), ('tokenizer_config.json', tokenizer_config))


_ONNX = {
    'tiny': ('onnx-community/whisper-tiny', 'ff4177021cc41f7db950912b73ea4fdf7d01d8e7', _onnx_common(2243, 3772, 282683),
             {'wasm': (('onnx/encoder_model_quantized.onnx', 10124990), ('onnx/decoder_model_merged_quantized.onnx', 30719241)),
              'webgpu': (('onnx/encoder_model.onnx', 32904992), ('onnx/decoder_model_merged_q4.onnx', 86713702))}),
    'base': ('onnx-community/whisper-base', '1846881b6b3a3024392c1eea3ad983695bc23925', _onnx_common(2243, 3832, 282682),
             {'wasm': (('onnx/encoder_model_quantized.onnx', 23201314), ('onnx/decoder_model_merged_quantized.onnx', 53693315)),
              'webgpu': (('onnx/encoder_model.onnx', 82468078), ('onnx/decoder_model_merged_q4.onnx', 123602419))}),
    'small': ('onnx-community/whisper-small', '36050c46d777d46dc4b5f43f6d90574fc38f8732', _onnx_common(2227, 3893, 282683),
              {'wasm': (('onnx/encoder_model_quantized.onnx', 92326160), ('onnx/decoder_model_merged_quantized.onnx', 156750845)),
               'webgpu': (('onnx/encoder_model.onnx', 352825870), ('onnx/decoder_model_merged_q4.onnx', 233149327))}),
}
VARIANTS = ('wasm', 'webgpu')
BROWSER_NAMES = tuple(_ONNX)
BROWSER: dict[tuple[str, str], Model] = {
    (name, variant): Model(name, repo, revision, (*common, *files[variant]))
    for name, (repo, revision, common, files) in _ONNX.items() for variant in VARIANTS}

# ONNX Runtime's WebAssembly binary, the one the vendored transformers.js 4.3.0 loads: too large to carry in the
# package (26 MB), so it is fetched with the first browser model, from the exact npm release, and checked by its hash.
RUNTIME_VERSION = '1.31.0-dev.20260914-8d85527a0'
RUNTIME_FILE = 'ort-wasm-simd-threaded.asyncify.wasm'
RUNTIME_SIZE = 26861777
RUNTIME_SHA256 = '49871f5a4409519797e127440868a6d1923339d9185907f301a5b2a1d90af082'
RUNTIME_URL = f'https://cdn.jsdelivr.net/npm/onnxruntime-web@{RUNTIME_VERSION}/dist/{RUNTIME_FILE}'


def root() -> Path:
    return home.home() / 'models'


def server_folder(model: Model) -> Path:
    return root() / 'whisper' / model.name


def browser_folder() -> Path:
    """Served to the page at /api/voice/files/: each repository under its own name, as transformers.js asks for it,
    and the runtime under runtime/."""
    return root() / 'browser'


def runtime_path() -> Path:
    return browser_folder() / 'runtime' / RUNTIME_VERSION / RUNTIME_FILE


def present(folder: Path, model: Model) -> bool:
    """Every file of the model is there at the size promised; a download cut short leaves only `.part` files."""
    return all((folder / name).is_file() and (folder / name).stat().st_size == size for name, size in model.files)


def browser_present(name: str, variant: str) -> dict[str, Any]:
    model = BROWSER[(name, variant)]
    runtime = runtime_path()
    have_runtime = runtime.is_file() and runtime.stat().st_size == RUNTIME_SIZE
    have_model = present(browser_folder() / model.repo, model)
    missing = (0 if have_model else model.size) + (0 if have_runtime else RUNTIME_SIZE)
    return {'model': name, 'variant': variant, 'repo': model.repo, 'present': have_model and have_runtime,
            'size': model.size + RUNTIME_SIZE, 'to_download': missing}


# What is being downloaded now, read by the status verb so the page can show its progress, keyed by what it fetches.
PROGRESS: dict[str, dict[str, Any]] = {}
_LOCK = threading.Lock()


def _fetch(url: str, target: Path, size: int, key: str, sha256: str | None = None,
           progressed: Callable[[dict[str, Any]], None] | None = None) -> None:
    """One file, streamed to `<target>.part` and renamed once it is whole, so a cut download is never read;
    `progressed` is told what has arrived as each chunk lands."""
    if target.is_file() and target.stat().st_size == size:
        PROGRESS[key]['done'] += size
        return
    private = home.is_home_path(target)
    if private:
        home.mkdir_private(target.parent)
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
    part = target.with_name(target.name + '.part')
    if private:
        home.write_private(part, b'')
    digest = hashlib.sha256()
    request = urllib.request.Request(url, headers={'User-Agent': 'metaform-voice'})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as answer, part.open('wb') as out:
        while chunk := answer.read(CHUNK):
            out.write(chunk)
            digest.update(chunk)
            PROGRESS[key]['done'] += len(chunk)
            if progressed is not None:
                progressed(status_of(key))
    arrived = part.stat().st_size
    if arrived != size:
        part.unlink(missing_ok=True)
        raise OSError(f'{target.name} arrived as {arrived} bytes, not {size}.')
    if sha256 is not None and digest.hexdigest() != sha256:
        part.unlink(missing_ok=True)
        raise OSError(f'{target.name} does not match its published SHA-256; it was not kept.')
    part.replace(target)


def download(key: str, jobs: list[tuple[str, Path, int, str | None]],
             progressed: Callable[[dict[str, Any]], None] | None = None) -> dict[str, Any]:
    """Fetch every job, `(url, target, size, sha256)`, once at a time per key; a second call while one runs waits for
    it rather than fetching the same files twice. `progressed` is told what has arrived as it arrives."""
    with _LOCK:
        running = PROGRESS.get(key)
        if running is not None and running.get('state') == 'running':
            event = running['event']
        else:
            event = None
            PROGRESS[key] = {'state': 'running', 'done': 0, 'total': sum(job[2] for job in jobs),
                             'started': time.time(), 'event': threading.Event()}
    if event is not None:
        event.wait()
        return status_of(key)
    try:
        for url, target, size, sha256 in jobs:
            _fetch(url, target, size, key, sha256, progressed)
        PROGRESS[key]['state'] = 'done'
    except Exception as error:  # noqa: BLE001  a failed download is reported, never half-kept
        PROGRESS[key].update(state='failed', error=str(error))
    finally:
        PROGRESS[key]['event'].set()
    return status_of(key)


def status_of(key: str) -> dict[str, Any]:
    found = PROGRESS.get(key)
    return {} if found is None else {k: v for k, v in found.items() if k != 'event'}


def server_jobs(model: Model) -> list[tuple[str, Path, int, str | None]]:
    folder = server_folder(model)
    return [(f'{HUB}/{model.repo}/resolve/{model.revision}/{name}', folder / name, size, None)
            for name, size in model.files]


def browser_jobs(name: str, variant: str) -> list[tuple[str, Path, int, str | None]]:
    model = BROWSER[(name, variant)]
    folder = browser_folder() / model.repo
    return [(RUNTIME_URL, runtime_path(), RUNTIME_SIZE, RUNTIME_SHA256),
            *((f'{HUB}/{model.repo}/resolve/{model.revision}/{file}', folder / file, size, None)
              for file, size in model.files)]


def remove_server(model: Model) -> bool:
    folder = server_folder(model)
    if not folder.exists():
        return False
    shutil.rmtree(folder)
    return True
