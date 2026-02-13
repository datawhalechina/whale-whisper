import assert from "node:assert/strict";

import {
  chunkTtsInput,
  toSpeakableTtsChunks,
  TTS_FLUSH_INSTRUCTION,
  TTS_SPECIAL_TOKEN,
} from "./tts-chunker.ts";

function run(name: string, fn: () => void) {
  try {
    fn();
    console.info(`PASS ${name}`);
  } catch (error) {
    console.error(`FAIL ${name}`);
    throw error;
  }
}

run("splits on hard punctuation", () => {
  const chunks = toSpeakableTtsChunks("你好。世界。");
  assert.deepEqual(chunks, ["你好。", "世界。"]);
});

run("keeps decimal punctuation in numbers", () => {
  const chunks = toSpeakableTtsChunks("价格是2.5，不是25。");
  assert.equal(chunks.join(""), "价格是2.5，不是25。");
});

run("normalizes three dots into ellipsis", () => {
  const chunks = toSpeakableTtsChunks("等等...快点。");
  assert.ok(chunks.join("").includes("…"));
  assert.equal(chunks.join("").includes("..."), false);
});

run("emits special reason when special token appears", () => {
  const chunks = chunkTtsInput(`前缀${TTS_SPECIAL_TOKEN}后缀。`);
  assert.equal(chunks[0]?.reason, "special");
  assert.equal(chunks[0]?.text, "前缀");
});

run("emits standalone special chunk when buffer is empty", () => {
  const chunks = chunkTtsInput(`${TTS_SPECIAL_TOKEN}你好。`);
  assert.equal(chunks[0]?.reason, "special");
  assert.equal(chunks[0]?.text, "");
});

run("flush instruction forces chunk boundary and is stripped for TTS text", () => {
  const chunks = toSpeakableTtsChunks(`第一句${TTS_FLUSH_INSTRUCTION}第二句。`);
  assert.deepEqual(chunks, ["第一句", "第二句。"]);
});
