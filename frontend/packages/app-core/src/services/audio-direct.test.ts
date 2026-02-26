import assert from "node:assert/strict";

import {
  buildDirectTtsHttpRequest,
  supportsDirectTts,
} from "../utils/tts-direct-request.ts";

function run(name: string, fn: () => void) {
  try {
    fn();
    console.info(`PASS ${name}`);
  } catch (error) {
    console.error(`FAIL ${name}`);
    throw error;
  }
}

run("supports direct tts for volcengine speech engine", () => {
  assert.equal(supportsDirectTts("volcengine-speech"), true);
  assert.equal(supportsDirectTts("openai-tts"), true);
  assert.equal(supportsDirectTts("alibaba-cloud-model-studio-speech"), true);
  assert.equal(supportsDirectTts("unknown-engine"), false);
});

run("builds direct volcengine request with unspeech extra_body appid", () => {
  const request = buildDirectTtsHttpRequest({
    text: "hello",
    engineId: "volcengine-speech",
    config: {
      apiKey: "token-123",
      baseUrl: "https://unspeech.hyp3r.link/v1/",
      model: "v1",
      voice: "zh_female_test",
      appId: "appid-xyz",
    },
  });

  assert.ok(request);
  assert.equal(request?.url, "https://unspeech.hyp3r.link/v1/audio/speech");
  assert.equal(request?.headers.Authorization, "Bearer token-123");
  assert.equal(request?.body.model, "volcengine/v1");
  assert.equal(request?.body.voice, "zh_female_test");
  assert.equal(
    (request?.body.extra_body as { app?: { appid?: string } })?.app?.appid,
    "appid-xyz"
  );
});

run("builds direct alibaba request and normalizes model prefix", () => {
  const request = buildDirectTtsHttpRequest({
    text: "hello",
    engineId: "alibaba-cloud-model-studio-speech",
    config: {
      apiKey: "token-123",
      baseUrl: "https://unspeech.hyp3r.link/v1/",
      model: "cosyvoice-v1",
      voice: "longxiaochun_v2",
      rate: 1.2,
      pitch: 0.9,
    },
  });

  assert.ok(request);
  assert.equal(request?.body.model, "alibaba/cosyvoice-v1");
  assert.equal(request?.body.voice, "longxiaochun_v2");
  assert.equal(
    (request?.body.extra_body as { rate?: number })?.rate,
    1.2
  );
});

run("builds direct openai-tts request", () => {
  const request = buildDirectTtsHttpRequest({
    text: "hello",
    engineId: "openai-tts",
    config: {
      apiKey: "sk-test",
      baseUrl: "https://api.openai.com/v1/",
      model: "tts-1",
      voice: "alloy",
      speed: 1.1,
    },
  });

  assert.ok(request);
  assert.equal(request?.url, "https://api.openai.com/v1/audio/speech");
  assert.equal(request?.body.model, "tts-1");
  assert.equal(request?.body.voice, "alloy");
});
