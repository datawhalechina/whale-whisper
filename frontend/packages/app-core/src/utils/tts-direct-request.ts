type AudioRequestConfig = Record<string, unknown>;

export type DirectTtsHttpRequest = {
  url: string;
  headers: Record<string, string>;
  body: Record<string, unknown>;
};

const directTtsEngineIds = new Set(["volcengine-speech"]);

function asRecord(value: unknown): Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function readString(config: Record<string, unknown>, keys: string[]) {
  for (const key of keys) {
    const value = config[key];
    if (typeof value === "string" && value.trim()) {
      return value.trim();
    }
  }
  return "";
}

function normalizeDirectSpeechUrl(baseUrl: string) {
  const trimmed = baseUrl.trim().replace(/\/+$/, "");
  return `${trimmed}/audio/speech`;
}

function resolveVolcengineAppId(config: Record<string, unknown>) {
  const topLevel = readString(config, ["appId", "appid", "app_id"]);
  if (topLevel) return topLevel;
  const app = asRecord(config.app);
  return readString(app, ["appId", "appid", "app_id"]);
}

function buildVolcengineExtraBody(config: Record<string, unknown>, appId: string) {
  const extraBody = asRecord(config.extra_body);
  const extraBodyFallback = asRecord(config.extraBody);
  const mergedExtraBody = {
    ...extraBodyFallback,
    ...extraBody,
  };
  const app = {
    ...asRecord(mergedExtraBody.app),
    ...asRecord(config.app),
    appid: appId,
    appId,
  };

  const audio = asRecord(config.audio);
  const request = asRecord(config.request);
  const user = asRecord(config.user);

  const output: Record<string, unknown> = {
    ...mergedExtraBody,
    app,
  };

  if (Object.keys(audio).length > 0) output.audio = audio;
  if (Object.keys(request).length > 0) output.request = request;
  if (Object.keys(user).length > 0) output.user = user;

  return output;
}

function normalizeModel(engineId: string, model: string) {
  if (engineId === "volcengine-speech" && !model.includes("/")) {
    return `volcengine/${model}`;
  }
  if (engineId === "alibaba-cloud-model-studio-speech" && !model.includes("/")) {
    return `alibaba/${model}`;
  }
  return model;
}

function buildAlibabaExtraBody(config: Record<string, unknown>) {
  const extraBody = asRecord(config.extra_body);
  const extraBodyFallback = asRecord(config.extraBody);
  const output: Record<string, unknown> = {
    ...extraBodyFallback,
    ...extraBody,
  };

  const numericFields: Array<[string, string]> = [
    ["rate", "rate"],
    ["pitch", "pitch"],
    ["volume", "volume"],
    ["sample_rate", "sample_rate"],
    ["sampleRate", "sample_rate"],
  ];
  for (const [source, target] of numericFields) {
    const value = config[source];
    if (typeof value === "number") {
      output[target] = value;
    }
  }

  return output;
}

export function supportsDirectTts(engineId: string | null | undefined) {
  if (!engineId) return false;
  if (engineId === "openai-tts") return true;
  if (engineId === "alibaba-cloud-model-studio-speech") return true;
  return directTtsEngineIds.has(engineId);
}

export function buildDirectTtsHttpRequest(input: {
  text: string;
  engineId?: string;
  config?: AudioRequestConfig;
}): DirectTtsHttpRequest | null {
  const engineId = (input.engineId || "").trim();
  if (!supportsDirectTts(engineId)) return null;

  const config = asRecord(input.config);
  const apiKey = readString(config, ["apiKey", "api_key"]);
  const baseUrl = readString(config, ["baseUrl", "base_url"]);
  const model = normalizeModel(engineId, readString(config, ["model"]));
  const voice = readString(config, ["voice"]);
  const text = (input.text || "").trim();

  if (!apiKey || !baseUrl || !model || !voice || !text) {
    return null;
  }

  const body: Record<string, unknown> = {
    model,
    input: text,
    voice,
  };

  const responseFormat = readString(config, ["response_format", "responseFormat", "format"]);
  if (responseFormat) {
    body.response_format = responseFormat;
  }

  const speed = config.speed;
  if (typeof speed === "number") {
    body.speed = speed;
  }

  if (engineId === "volcengine-speech") {
    const appId = resolveVolcengineAppId(config);
    if (!appId) return null;
    body.backend = readString(config, ["backend"]) || "volcengine";
    body.extra_body = buildVolcengineExtraBody(config, appId);
  } else if (engineId === "alibaba-cloud-model-studio-speech") {
    const extraBody = buildAlibabaExtraBody(config);
    if (Object.keys(extraBody).length > 0) {
      body.extra_body = extraBody;
    }
  }

  return {
    url: normalizeDirectSpeechUrl(baseUrl),
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${apiKey}`,
    },
    body,
  };
}
