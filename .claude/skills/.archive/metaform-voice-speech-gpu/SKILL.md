---
name: metaform-voice-speech-gpu
description: Use when Whisper CUDA 400s or voice GPU goes unused.
category: development
---

# Metaform voice: CUDA load check and the page server's environment

The server engine (`src/metaform/modules/voice/engine.py`) may pick CUDA only after cuBLAS 12 actually loads (`libcublas.so.12`, or `cublas64_12.dll` on Windows). A GPU that is counted but whose libraries are gone makes every utterance fail, so the check must dlopen the library. When it fails, the engine runs Whisper on the CPU in int8 and status carries `server.cuda_error`, the install step and a reason.

- Test a GPU-path change with the wheels hidden: a `sys.meta_path` finder answering `ModuleSpec('nvidia', None)` for `nvidia`, then confirm status reports the cuBLAS failure and the wav still transcribes on the CPU. Test the CUDA path with the wheels present.
- The page server runs under the Python that ran `metaform web start`. On this machine that is the uv tool install (`~/.local/share/uv/tools/metaform`), not the repo `.venv`. Add the extra to the tool with `uv tool install --editable '/home/rich/metaform[voice-gpu]'` so its receipt keeps `voice-gpu`.
- In the repo, sync with `uv sync --extra dev --extra voice-gpu --inexact`. A plain `uv sync --extra dev` removes the GPU wheels; `--inexact` removes nothing other agents installed.
- Restart the server with `~/.local/bin/metaform web stop`, then `web start`, from the project folder.
- Live check: POST a 1 s 16 kHz wav to `/api/voice/transcribe?partial=0` with `Origin`, `Referer` and `Sec-Fetch-Site: same-origin` headers, and confirm `device` is `cuda` or, after hiding the wheels, `cpu`.
- Do not add an install hint on the not-installed-with-GPU path in `engine.py`; the general install text is what the existing tests pin on GPU hosts.
- Voice notes in `voice.js` stay until dismissed and go to `POST /api/voice/note`. The page re-reads status on `metaform:reconnected`. Keep capture code (`openMic`, `captured`, `voice-capture.js`) out of note or status edits.
