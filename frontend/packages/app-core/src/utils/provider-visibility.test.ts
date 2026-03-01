import assert from "node:assert/strict";

import {
  filterVisibleSpeechProviders,
  isVisibleSpeechProviderId,
} from "./provider-visibility.ts";

function run(name: string, fn: () => void) {
  try {
    fn();
    console.info(`PASS ${name}`);
  } catch (error) {
    console.error(`FAIL ${name}`);
    throw error;
  }
}

run("only configured speech providers are visible", () => {
  assert.equal(isVisibleSpeechProviderId("volcengine-speech"), true);
  assert.equal(isVisibleSpeechProviderId("alibaba-cloud-model-studio-speech"), true);
  assert.equal(isVisibleSpeechProviderId("browser-local-audio-speech"), true);
  assert.equal(isVisibleSpeechProviderId("app-local-audio-speech"), true);
  assert.equal(isVisibleSpeechProviderId("openai-audio-speech"), false);
  assert.equal(isVisibleSpeechProviderId("elevenlabs"), false);
});

run("filters unsupported speech provider ids", () => {
  assert.deepEqual(
    filterVisibleSpeechProviders([
      "openai-audio-speech",
      "volcengine-speech",
      "alibaba-cloud-model-studio-speech",
      "elevenlabs",
      "browser-local-audio-speech",
    ]),
    [
      "volcengine-speech",
      "alibaba-cloud-model-studio-speech",
      "browser-local-audio-speech",
    ]
  );
});
