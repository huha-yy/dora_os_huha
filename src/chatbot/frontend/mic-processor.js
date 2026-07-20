/**
 * Dorabot Microphone AudioWorklet Processor
 * 
 * Captures raw PCM audio from the microphone stream and sends chunks
 * to the main thread via postMessage. Accumulates 4096 samples per chunk
 * to match the backend VAD buffer size.
 * 
 * Sample rate: 16000 Hz → 4096 samples = 256ms per chunk
 */

const CHUNK_SIZE = 4096;

class MicProcessor extends AudioWorkletProcessor {
    constructor() {
        super();
        this.buffer = new Float32Array(CHUNK_SIZE);
        this.offset = 0;
        this.port.postMessage({ type: 'ready' });
    }

    process(inputs) {
        const input = inputs[0];
        if (!input || !input[0] || input[0].length === 0) {
            return true;
        }

        const channelData = input[0];
        const inputLength = channelData.length;

        let remaining = inputLength;
        let srcOffset = 0;

        while (remaining > 0) {
            const space = CHUNK_SIZE - this.offset;
            const copy = Math.min(space, remaining);

            for (let i = 0; i < copy; i++) {
                this.buffer[this.offset + i] = channelData[srcOffset + i];
            }
            this.offset += copy;
            srcOffset += copy;
            remaining -= copy;

            if (this.offset >= CHUNK_SIZE) {
                const chunk = new Float32Array(CHUNK_SIZE);
                chunk.set(this.buffer);
                this.port.postMessage({ type: 'audio-chunk', audio: chunk });
                this.offset = 0;
            }
        }

        return true;
    }
}

registerProcessor('mic-processor', MicProcessor);
