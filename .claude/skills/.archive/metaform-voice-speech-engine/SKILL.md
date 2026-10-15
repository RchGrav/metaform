---
name: metaform-voice-speech-engine
description: Use when Whisper fails on CUDA, voice-gpu is missing, the GPU goes unused, or transcripts come out as "you" or garbled.
category: development
---

# Metaform voice engine: pick CUDA only after cuBLAS loads

A GPU that is counted but whose CUDA libraries are gone makes every utterance fail. The engine must dlopen cuBLAS 12 before it chooses CUDA, and fall back to CPU int8 with the reason when that load fails.

- Probe the library, not the count. `engine.machine()` checks the device count, then `_cuda_loads()`, which preloads the nvidia-* wheels and dlopens `libcublas.so.12` (`cublas64_12.dll` on Windows). It runs once per process.
- On failure: cuda count 0, `status.server.cuda_error` carries the loader message, `install` is the `uv sync --extra voice-gpu` step, and the reason says the CPU runs it in int8.
- Probe only cuBLAS. ctranslate2 4.8 references no cuDNN; its CUDA dependencies are libcublas and libcuda.
- The page server runs on whichever Python ran `metaform web start`. On this machine that is the uv tool install, so its receipt must list `voice-gpu`.
- In the repo venv use `uv sync --extra dev --extra voice-gpu --inexact`. A plain `uv sync --extra dev` removes the GPU wheels; `--inexact` removes nothing other agents installed.
- Restart after an engine change: `metaform web stop`, then `metaform web start`, from the project folder. Confirm one `web.server` process.
- Live check: POST a 1 s 16 kHz wav to `/api/voice/transcribe?partial=0` with Origin, Referer and Sec-Fetch-Site same-origin headers. Compare `device` in the answer with `status.server.device`.
- To test the fallback without touching the shared venv, import `scripts/hide_nvidia_wheels.py` first in the process under test. Then only cuBLAS 11 is found, and the dlopen fails as it would without the wheel.
- Do not add an install hint on the not-installed-with-GPU path in `engine.py`; the general install text is what the existing tests pin on GPU hosts.

## Stock words and garbled text on a working GPU
- Whisper turns silence and noise into stock words, usually `you` or `Thank you`. Treat that as silence first, not as a model fault: check `no_speech_prob` per segment before the text reaches the page.
- Short clips with the language left on `auto` are guessed badly. Pass the language the person speaks explicitly.
- Keep each utterance's text and the engine that produced it, so the next mishearing can be traced. Prove a change with a silent wav and a known sentence before reporting it.
