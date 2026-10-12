/* The browser engine of voice: Whisper run in this page's own worker with transformers.js, so speech is heard on the
 * device and the audio goes nowhere. The model's files and ONNX Runtime's WebAssembly binary are read from this
 * server, /api/voice/files/, where the voice module downloaded them once after the person agreed; nothing is fetched
 * from anywhere else. WebGPU runs it where the browser has it; WebAssembly everywhere else.
 *
 * Messages in: {type: 'load', repo, variant, runtime} and {type: 'run', id, audio, partial, language}.
 * Messages out: {type: 'loaded', took}, {type: 'result', id, text, took}, {type: 'error', id, message}. */
import {pipeline, env} from '/vendor/transformers/transformers.min.js';

env.allowRemoteModels = false;
env.allowLocalModels = true;
env.localModelPath = '/api/voice/files/';
env.useBrowserCache = false;  // the server's own copy answers with an immutable cache header; one copy is enough
env.useWasmCache = false;  // its cache re-imports the runtime from a blob: URL, which the page's policy refuses

const DTYPES = {
  wasm: {encoder_model: 'q8', decoder_model_merged: 'q8'},
  webgpu: {encoder_model: 'fp32', decoder_model_merged: 'q4'},
};
let heard = null, loading = null;

async function load({repo, variant, runtime}) {
  // The runtime's JavaScript glue ships with the page; its WebAssembly binary was downloaded with the model.
  env.backends.onnx.wasm.wasmPaths = {mjs: '/vendor/transformers/ort-wasm-simd-threaded.asyncify.mjs', wasm: runtime};
  // Threads need a cross-origin isolated page, which this one is not; one thread is asked for so none is tried.
  if (!self.crossOriginIsolated) env.backends.onnx.wasm.numThreads = 1;
  const began = performance.now();
  heard = await pipeline('automatic-speech-recognition', repo, {device: variant, dtype: DTYPES[variant]});
  return performance.now() - began;
}

self.onmessage = async ({data}) => {
  if (data.type === 'load') {
    try {
      loading = loading || load(data);
      const took = await loading;
      self.postMessage({type: 'loaded', took});
    } catch (error) {
      loading = null;
      self.postMessage({type: 'error', id: null, message: String(error?.message || error)});
    }
    return;
  }
  if (data.type !== 'run') return;
  try {
    await loading;
    const began = performance.now();
    const long = data.audio.length > 30 * 16000;
    const out = await heard(data.audio, {
      task: 'transcribe', ...(data.language ? {language: data.language} : {}),
      ...(long ? {chunk_length_s: 30, stride_length_s: 5} : {}),
      ...(data.partial ? {num_beams: 1} : {}),
    });
    const text = (Array.isArray(out) ? out.map(one => one.text).join(' ') : out.text || '').trim();
    self.postMessage({type: 'result', id: data.id, text, took: performance.now() - began});
  } catch (error) {
    self.postMessage({type: 'error', id: data.id, message: String(error?.message || error)});
  }
};
