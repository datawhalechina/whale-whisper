import assert from "node:assert/strict";

import { sanitizeTranscript } from "./transcript-filter.ts";

function run(name: string, fn: () => void) {
  try {
    fn();
    console.info(`PASS ${name}`);
  } catch (error) {
    console.error(`FAIL ${name}`);
    throw error;
  }
}

run("drops windows absolute image path transcript", () => {
  const transcript = String.raw`C:\Users\ADMIN\Documents\WeChat Files\wxid_b2orpigekka622\FileStorage\Temp\1772262785183.jpg`;
  assert.equal(sanitizeTranscript(transcript), "");
});

run("keeps normal natural language transcript", () => {
  assert.equal(sanitizeTranscript("你好，这是语音测试。"), "你好，这是语音测试。");
});

