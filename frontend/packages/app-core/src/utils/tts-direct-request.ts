type AudioRequestConfig = Record<string, unknown>;

type BackendTtsPayload = {
  engine: string;
  data: string;
  config: Record<string, unknown>;
};

type LegacyTtsPayload = {
  text: string;
  engine: string;
  providerId?: string;
  provider_id?: string;
  config: Record<string, unknown>;
};

export type DirectTtsHttpRequest = {
  url: string;
  headers: Record<string, string>;
  body: BackendTtsPayload;
};

export type LegacyTtsHttpRequest = {
  url: string;
  headers: Record<string, string>;
  body: LegacyTtsPayload;
};

const allowedBackendTtsEngineIds = new Set([
  "volcengine-speech",
  "alibaba-cloud-model-studio-speech",
]);
const legacyUnspeechHost = "unspeech.hyp3r.link";

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

function normalizeBackendTtsUrl(apiBaseUrl: string) {
  const trimmed = apiBaseUrl.trim().replace(/\/+$/, "");
  return `${trimmed}/api/tts/engines`;
}

function normalizeLegacyTtsUrl(url: string) {
  const trimmed = url.trim().replace(/\/+$/, "");
  if (trimmed.endsWith("/api/tts/engines")) {
    return `${trimmed.slice(0, -"/api/tts/engines".length)}/api/tts/synthesize`;
  }
  return `${trimmed}/api/tts/synthesize`;
}

function resolveLegacyBackend(engineId: string) {
  if (engineId === "volcengine-speech") return "volcengine";
  if (engineId === "alibaba-cloud-model-studio-speech") return "alibaba";
  return "";
}

function normalizeAlibabaModelId(model: string, engineId: string) {
  if (engineId !== "alibaba-cloud-model-studio-speech") {
    return model;
  }
  return model.replace(/^alibaba\//i, "").trim();
}

function normalizeLegacyUnspeechBaseUrl(engineId: string, baseUrl: string) {
  const normalized = baseUrl.trim();
  if (!normalized) return normalized;

  try {
    const parsed = new URL(normalized);
    if (parsed.hostname.toLowerCase() !== legacyUnspeechHost) {
      return normalized;
    }
  } catch {
    return normalized;
  }

  if (engineId === "volcengine-speech") {
    return "https://openspeech.bytedance.com/api/v1/tts";
  }
  if (engineId === "alibaba-cloud-model-studio-speech") {
    return "https://dashscope.aliyuncs.com";
  }
  return normalized;
}

function resolveVolcengineAppId(config: Record<string, unknown>) {
  const topLevel = readString(config, ["appId", "appid", "app_id"]);
  if (topLevel) return topLevel;
  const app = asRecord(config.app);
  return readString(app, ["appId", "appid", "app_id"]);
}

function copyKnownExtras(
  source: Record<string, unknown>,
  target: Record<string, unknown>,
  keys: string[]
) {
  keys.forEach((key) => {
    if (Object.prototype.hasOwnProperty.call(source, key) && source[key] !== undefined) {
      target[key] = source[key];
    }
  });
}

export function supportsDirectTts(engineId: string | null | undefined) {
  if (!engineId) return false;
  return allowedBackendTtsEngineIds.has(engineId);
}

export function buildDirectTtsHttpRequest(input: {
  text: string;
  engineId?: string;
  apiBaseUrl?: string;
  config?: AudioRequestConfig;
}): DirectTtsHttpRequest | null {
  const engineId = (input.engineId || "").trim();
  if (!supportsDirectTts(engineId)) return null;

  const config = asRecord(input.config);
  const apiBaseUrl = (input.apiBaseUrl || "").trim();
  const apiKey = readString(config, ["apiKey", "api_key"]);
  const baseUrl = normalizeLegacyUnspeechBaseUrl(
    engineId,
    readString(config, ["baseUrl", "base_url"])
  );
  const model = normalizeAlibabaModelId(readString(config, ["model"]), engineId);
  const voice = readString(config, ["voice"]);
  const text = (input.text || "").trim();

  if (!apiBaseUrl || !apiKey || !model || !voice || !text) {
    return null;
  }

  const backendConfig: Record<string, unknown> = {
    apiKey,
    model,
    voice,
  };

  if (baseUrl) {
    backendConfig.baseUrl = baseUrl;
  }

  const responseFormat = readString(config, ["response_format", "responseFormat", "format"]);
  if (responseFormat) {
    backendConfig.response_format = responseFormat;
  }

  if (typeof config.speed === "number") {
    backendConfig.speed = config.speed;
  }

  if (engineId === "volcengine-speech") {
    const appId = resolveVolcengineAppId(config);
    if (!appId) return null;
    backendConfig.appId = appId;
    copyKnownExtras(config, backendConfig, [
      "app",
      "audio",
      "request",
      "user",
      "extra_body",
      "extraBody",
    ]);
  }

  if (engineId === "alibaba-cloud-model-studio-speech") {
    copyKnownExtras(config, backendConfig, [
      "rate",
      "pitch",
      "volume",
      "sample_rate",
      "sampleRate",
      "extra_body",
      "extraBody",
    ]);
  }

  return {
    url: normalizeBackendTtsUrl(apiBaseUrl),
    headers: {
      "Content-Type": "application/json",
    },
    body: {
      engine: engineId,
      data: text,
      config: backendConfig,
    },
  };
}

export function buildLegacyTtsHttpRequest(input: DirectTtsHttpRequest): LegacyTtsHttpRequest {
  const config: Record<string, unknown> = {
    ...input.body.config,
  };
  const apiKey = readString(config, ["apiKey", "api_key"]);
  if (apiKey && !readString(config, ["api_key"])) {
    config.api_key = apiKey;
  }

  const baseUrl = readString(config, ["baseUrl", "base_url"]);
  if (baseUrl) {
    if (!readString(config, ["baseUrl"])) {
      config.baseUrl = baseUrl;
    }
    if (!readString(config, ["base_url"])) {
      config.base_url = baseUrl;
    }
  }

  const backend = resolveLegacyBackend(input.body.engine);
  if (backend && !readString(config, ["backend"])) {
    config.backend = backend;
  }

  const model = readString(config, ["model"]);
  if (model && !model.includes("/")) {
    if (backend === "volcengine") {
      config.model = `volcengine/${model}`;
    }
  }
  if (backend === "alibaba") {
    config.model = normalizeAlibabaModelId(readString(config, ["model"]), input.body.engine);
  }

  const appId = readString(config, ["appId", "appid", "app_id"]);
  if (appId) {
    if (!readString(config, ["appid"])) {
      config.appid = appId;
    }
    if (!readString(config, ["app_id"])) {
      config.app_id = appId;
    }
  }

  return {
    url: normalizeLegacyTtsUrl(input.url),
    headers: {
      ...input.headers,
    },
    body: {
      text: input.body.data,
      engine: input.body.engine,
      providerId: input.body.engine,
      provider_id: input.body.engine,
      config,
    },
  };
}
