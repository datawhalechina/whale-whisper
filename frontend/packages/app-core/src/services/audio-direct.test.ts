import assert from "node:assert/strict";

import {
  buildLegacyTtsHttpRequest,
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

run("supports backend relay tts engines", () => {
  assert.equal(supportsDirectTts("volcengine-speech"), true);
  assert.equal(supportsDirectTts("alibaba-cloud-model-studio-speech"), true);
  assert.equal(supportsDirectTts("openai-tts"), false);
  assert.equal(supportsDirectTts("unknown-engine"), false);
});

run("builds backend relay request for volcengine speech engine", () => {
  const request = buildDirectTtsHttpRequest({
    text: "hello",
    engineId: "volcengine-speech",
    apiBaseUrl: "http://localhost:8090",
    config: {
      apiKey: "token-123",
      model: "v1",
      voice: "zh_female_test",
      appId: "appid-xyz",
    },
  });

  assert.ok(request);
  assert.equal(request?.url, "http://localhost:8090/api/tts/engines");
  assert.equal(request?.headers.Authorization, undefined);
  assert.deepEqual(request?.body, {
    engine: "volcengine-speech",
    data: "hello",
    config: {
      apiKey: "token-123",
      model: "v1",
      voice: "zh_female_test",
      appId: "appid-xyz",
    },
  });
});

run("builds backend relay request for alibaba speech engine", () => {
  const request = buildDirectTtsHttpRequest({
    text: "hello",
    engineId: "alibaba-cloud-model-studio-speech",
    apiBaseUrl: "http://localhost:8090/",
    config: {
      apiKey: "token-123",
      model: "alibaba/cosyvoice-v1",
      voice: "longxiaochun_v2",
      rate: 1.2,
      pitch: 0.9,
    },
  });

  assert.ok(request);
  assert.equal(request?.url, "http://localhost:8090/api/tts/engines");
  assert.deepEqual(request?.body, {
    engine: "alibaba-cloud-model-studio-speech",
    data: "hello",
    config: {
      apiKey: "token-123",
      model: "cosyvoice-v1",
      voice: "longxiaochun_v2",
      rate: 1.2,
      pitch: 0.9,
    },
  });
});

run("does not forward base url for fixed direct providers", () => {
  const volcRequest = buildDirectTtsHttpRequest({
    text: "hello",
    engineId: "volcengine-speech",
    apiBaseUrl: "http://localhost:8090",
    config: {
      apiKey: "token-123",
      baseUrl: "https://unspeech.hyp3r.link/v1/",
      model: "v1",
      voice: "zh_female_test",
      appId: "appid-xyz",
    },
  });
  assert.ok(volcRequest);
  assert.equal((volcRequest?.body.config as { baseUrl?: string }).baseUrl, undefined);

  const alibabaRequest = buildDirectTtsHttpRequest({
    text: "hello",
    engineId: "alibaba-cloud-model-studio-speech",
    apiBaseUrl: "http://localhost:8090",
    config: {
      apiKey: "token-123",
      baseUrl: "https://unspeech.hyp3r.link/v1/",
      model: "cosyvoice-v1",
      voice: "longwan",
    },
  });
  assert.ok(alibabaRequest);
  assert.equal((alibabaRequest?.body.config as { baseUrl?: string }).baseUrl, undefined);
});

run("builds legacy synthesize fallback request from backend relay request", () => {
  const request = buildDirectTtsHttpRequest({
    text: "fallback test",
    engineId: "volcengine-speech",
    apiBaseUrl: "http://localhost:8090",
    config: {
      apiKey: "token-123",
      baseUrl: "https://unspeech.example/v1",
      model: "v1",
      voice: "zh_female_test",
      appId: "appid-xyz",
    },
  });

  assert.ok(request);
  const legacy = buildLegacyTtsHttpRequest(request!);
  assert.equal(legacy.url, "http://localhost:8090/api/tts/synthesize");
  assert.deepEqual(legacy.body, {
    text: "fallback test",
    engine: "volcengine-speech",
    providerId: "volcengine-speech",
    provider_id: "volcengine-speech",
    config: {
      apiKey: "token-123",
      api_key: "token-123",
      model: "volcengine/v1",
      voice: "zh_female_test",
      appId: "appid-xyz",
      appid: "appid-xyz",
      app_id: "appid-xyz",
      backend: "volcengine",
    },
  });
});

run("keeps alibaba model id without provider prefix in legacy fallback request", () => {
  const request = buildDirectTtsHttpRequest({
    text: "fallback alibaba",
    engineId: "alibaba-cloud-model-studio-speech",
    apiBaseUrl: "http://localhost:8090",
    config: {
      apiKey: "token-123",
      model: "alibaba/cosyvoice-v1",
      voice: "longxiaochun_v2",
    },
  });

  assert.ok(request);
  const legacy = buildLegacyTtsHttpRequest(request!);
  assert.equal((legacy.body.config as { model?: string }).model, "cosyvoice-v1");
});
