import {
  chunkTtsInput,
  sanitizeTtsChunk,
  TTS_FLUSH_INSTRUCTION,
  TTS_SPECIAL_TOKEN,
} from "./tts-chunker.ts";

function endsWithControlMarker(text: string) {
  return (
    text.endsWith(TTS_FLUSH_INSTRUCTION) ||
    text.endsWith(TTS_SPECIAL_TOKEN)
  );
}

export class TtsStreamSegmenter {
  private input = "";
  private emittedCount = 0;

  appendLiteral(text: string) {
    if (!text) return;
    this.input += text;
  }

  appendSpecialMarker() {
    this.input += TTS_SPECIAL_TOKEN;
  }

  appendFlushMarker() {
    this.input += TTS_FLUSH_INSTRUCTION;
  }

  reset() {
    this.input = "";
    this.emittedCount = 0;
  }

  drain(finalize: boolean) {
    const chunks = chunkTtsInput(this.input);
    if (chunks.length === 0) return [];

    let emitUntil = chunks.length;
    if (!finalize) {
      const last = chunks[chunks.length - 1];
      if (last?.reason === "flush" && !endsWithControlMarker(this.input)) {
        emitUntil -= 1;
      }
    }

    if (emitUntil <= this.emittedCount) {
      return [];
    }

    const emitted: string[] = [];
    for (let index = this.emittedCount; index < emitUntil; index++) {
      const text = sanitizeTtsChunk(chunks[index]?.text ?? "");
      if (text) {
        emitted.push(text);
      }
    }

    this.emittedCount = emitUntil;
    return emitted;
  }
}
