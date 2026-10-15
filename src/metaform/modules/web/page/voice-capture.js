/* Voice capture: the microphone's samples, taken on the audio rendering thread so they never wait on the map's frames.
 *
 * voice.js loads this into its AudioContext with audioWorklet.addModule and connects the microphone to a 'voice-capture'
 * node. The context runs at 16 kHz, Whisper's rate, where the browser allows it; at any other rate each span of input
 * is averaged into one 16 kHz sample, a low-pass and a decimation in one, carried across render quanta. The samples are
 * gathered into blocks of BLOCK, about 85 ms, and each full block is sent to the page as a transferred buffer; the page
 * sends it back once it has copied it, so the same few buffers go round and nothing is made per block. A buffer is made
 * only when every one is still with the page, and then it stays in the pool. */

const SR = 16000;
const BLOCK = 1360;  // samples per block at 16 kHz, 85 ms
const POOL = 8;      // buffers made at the start

class VoiceCapture extends AudioWorkletProcessor {
  constructor() {
    super();
    this.ratio = sampleRate / SR;  // input samples per output sample; 1 when the context runs at 16 kHz
    this.pool = [];
    for (let i = 0; i < POOL; i++) this.pool.push(new Float32Array(BLOCK));
    this.block = this.pool.pop();
    this.at = 0;                   // samples filled in this.block
    this.sum = 0;                  // the span being averaged, when the context is not at 16 kHz
    this.count = 0;
    this.taken = 0;                // input samples read, in all
    this.made = 0;                 // output samples made, in all
    this.edge = Math.floor(this.ratio);  // the input sample at which the next output sample is complete
    this.transfer = [null];
    this.port.onmessage = event => { this.pool.push(event.data); };  // a block back from the page, free again
  }
  send() {
    const block = this.block;
    this.transfer[0] = block.buffer;
    this.port.postMessage(block, this.transfer);
    this.transfer[0] = null;
    this.block = this.pool.length ? this.pool.pop() : new Float32Array(BLOCK);
    this.at = 0;
  }
  process(inputs) {
    const channel = inputs[0][0];
    if (channel === undefined) return true;  // not connected yet, or already let go
    const length = channel.length;
    if (this.ratio === 1) {
      for (let i = 0; i < length; i++) {
        this.block[this.at++] = channel[i];
        if (this.at === BLOCK) this.send();
      }
      return true;
    }
    const ratio = this.ratio;
    let sum = this.sum, count = this.count, taken = this.taken, edge = this.edge;
    for (let i = 0; i < length; i++) {
      sum += channel[i];
      count++;
      taken++;
      if (taken < edge) continue;
      this.block[this.at++] = sum / count;
      sum = 0;
      count = 0;
      edge = Math.floor(++this.made * ratio + ratio);
      if (this.at === BLOCK) this.send();
    }
    this.sum = sum; this.count = count; this.taken = taken; this.edge = edge;
    return true;
  }
}
registerProcessor('voice-capture', VoiceCapture);
