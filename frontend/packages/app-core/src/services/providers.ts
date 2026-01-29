import type { ProviderConfig } from "../stores/providers";
import type { ProviderCatalogEntry, ProviderCategory, SelectOption } from "../data/provider-catalog";
import type { UnAlibabaCloudOptions, VoiceProviderWithExtraOptions } from "unspeech";

import { createUnAlibabaCloud, listVoices } from "unspeech";

import { appConfig } from "../config";

const proxyBaseUrl = appConfig.providers.proxyUrl?.trim();
const apiBaseUrl = appConfig.providers.apiBaseUrl?.trim();

function normalizeBaseUrl(input?: string, fallback?: string) {
  const raw = (input || fallback || "").trim();
  if (!raw) return "";
  return raw.endsWith("/") ? raw : `${raw}/`;
}

function resolveFieldDefault(option: ProviderCatalogEntry | undefined, fieldId: string) {
  const field = option?.fields?.find((item) => item.id === fieldId);
  if (!field || field.default === undefined || field.default === null) return "";
  return String(field.default);
}

function resolveDefaultBaseUrl(option: ProviderCatalogEntry | undefined) {
  return option?.defaults?.baseUrl || resolveFieldDefault(option, "baseUrl");
}

async function requestProxy<T>(path: string, body: Record<string, unknown>) {
  if (!proxyBaseUrl) {
    throw new Error("Provider proxy is not configured.");
  }

  const url = `${proxyBaseUrl.replace(/\/$/, "")}${path}`;
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    throw new Error(`Provider proxy error: ${response.status}`);
  }

  return (await response.json()) as T;
}

function resolveApiBaseUrl() {
  if (proxyBaseUrl) {
    return proxyBaseUrl.replace(/\/$/, "");
  }
  if (apiBaseUrl) {
    return apiBaseUrl.replace(/\/$/, "");
  }
  return "";
}

function categoryToEnginePath(category: ProviderCategory) {
  if (category === "chat") return "llm";
  if (category === "speech") return "tts";
  return "asr";
}

export async function checkEngineHealth(
  category: ProviderCategory,
  engineId: string,
  config?: ProviderConfig,
) {
  const baseUrl = resolveApiBaseUrl();
  const path = `/api/${categoryToEnginePath(category)}/engines/${engineId}/health`;
  
  let response: Response;
  if (config) {
    // 使用 POST 方法传递配置
    const requestBody = {
      config: {
        apiKey: config.apiKey,
        baseUrl: config.baseUrl,
        ...config.extra,
      },
    };
    response = await fetch(`${baseUrl}${path}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(requestBody),
    });
  } else {
    // 使用 GET 方法（向后兼容）
    response = await fetch(`${baseUrl}${path}`);
  }
  
  if (!response.ok) {
    throw new Error(`Health check failed: ${response.status}`);
  }
  try {
    return (await response.json()) as {
      ok: boolean;
      status_code?: number | null;
      message?: string;
      latency_ms?: number | null;
    };
  } catch {
    throw new Error("Health check returned non-JSON response. Check API base URL.");
  }
}

export async function validateProvider(option: ProviderCatalogEntry, config: ProviderConfig) {
  if (!proxyBaseUrl) {
    return { valid: true, reason: "" };
  }

  return await requestProxy<{ valid: boolean; reason?: string }>("/providers/validate", {
    providerId: option.id,
    apiKey: config.apiKey ?? "",
    baseUrl: normalizeBaseUrl(config.baseUrl, resolveDefaultBaseUrl(option)),
    extra: config.extra ?? {},
  });
}

export async function listProviderModels(option: ProviderCatalogEntry, config: ProviderConfig) {
  if (!proxyBaseUrl) {
    return null;
  }

  const result = await requestProxy<{ models?: SelectOption[]; data?: { models?: SelectOption[] } }>(
    "/api/providers/models",
    {
      providerId: option.id,
      apiKey: config.apiKey ?? "",
      baseUrl: normalizeBaseUrl(config.baseUrl, resolveDefaultBaseUrl(option)),
      extra: config.extra ?? {},
    }
  );

  if (result.data?.models) return result.data.models;
  if (result.models) return result.models;
  return [];
}

export async function listProviderVoices(option: ProviderCatalogEntry, config: ProviderConfig) {
  if (!proxyBaseUrl) {
    if (option.id === "alibaba-cloud-model-studio-speech") {
      const apiKey = config.apiKey?.trim();
      const baseUrl = normalizeBaseUrl(config.baseUrl, resolveDefaultBaseUrl(option));
      if (!apiKey || !baseUrl) {
        return [];
      }
      const provider = createUnAlibabaCloud(apiKey, baseUrl) as VoiceProviderWithExtraOptions<UnAlibabaCloudOptions>;
      const voices = await listVoices({
        ...provider.voice(),
      });
      const configuredModel = config.model?.trim();
      const modelCandidates = new Set<string>();
      if (configuredModel) {
        modelCandidates.add(configuredModel);
        if (configuredModel.includes("/")) {
          const shortModel = configuredModel.split("/").pop();
          if (shortModel) {
            modelCandidates.add(shortModel);
          }
        } else {
          modelCandidates.add(`alibaba/${configuredModel}`);
        }
      }
      const filtered = voices.filter((voice) => {
        const compatible = voice.compatible_models;
        if (!Array.isArray(compatible) || compatible.length === 0) {
          return true;
        }
        if (!modelCandidates.size) {
          return true;
        }
        return compatible.some((model) => modelCandidates.has(model));
      });
      const resolved = filtered.length ? filtered : voices;
      return resolved.map((voice) => {
        const descriptions: string[] = [];
        if (voice.languages?.length) {
          descriptions.push(voice.languages.map((lang) => lang.title).join(", "));
        }
        if (Array.isArray(voice.compatible_models) && voice.compatible_models.length) {
          descriptions.push(`Models: ${voice.compatible_models.join(", ")}`);
        }
        return {
          id: voice.id,
          label: voice.name,
          description: descriptions.join(" · "),
        };
      });
    }
    return null;
  }

  const result = await requestProxy<{ voices?: SelectOption[]; data?: { voices?: SelectOption[] } }>(
    "/providers/voices",
    {
      providerId: option.id,
      apiKey: config.apiKey ?? "",
      baseUrl: normalizeBaseUrl(config.baseUrl, resolveDefaultBaseUrl(option)),
      extra: config.extra ?? {},
    }
  );

  if (result.data?.voices) return result.data.voices;
  if (result.voices) return result.voices;
  return [];
}
