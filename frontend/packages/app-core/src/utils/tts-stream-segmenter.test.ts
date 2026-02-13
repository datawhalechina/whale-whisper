import assert from "node:assert/strict";

import { TtsStreamSegmenter } from "./tts-stream-segmenter.ts";

function run(name: string, fn: () => void) {
  try {
    fn();
    console.info(`PASS ${name}`);
  } catch (error) {
    console.error(`FAIL ${name}`);
    throw error;
  }
}

run("emits finished sentence while keeping trailing tail", () => {
  const segmenter = new TtsStreamSegmenter();
  segmenter.appendLiteral("你好");
  assert.deepEqual(segmenter.drain(false), []);

  segmenter.appendLiteral("。世界");
  assert.deepEqual(segmenter.drain(false), ["你好。"]);

  segmenter.appendLiteral("。");
  assert.deepEqual(segmenter.drain(false), ["世界。"]);
});

run("special marker flushes previous literal chunk", () => {
  const segmenter = new TtsStreamSegmenter();
  segmenter.appendLiteral("前缀");
  segmenter.appendSpecialMarker();
  assert.deepEqual(segmenter.drain(false), ["前缀"]);
});

run("final drain emits tail chunk", () => {
  const segmenter = new TtsStreamSegmenter();
  segmenter.appendLiteral("还没结束");
  assert.deepEqual(segmenter.drain(false), []);
  assert.deepEqual(segmenter.drain(true), ["还没结束"]);
});
