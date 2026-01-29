import { useDebounceFn, useLocalStorage } from "@vueuse/core";
import { defineStore } from "pinia";
import { computed, ref, watch } from "vue";

import type {
  ProviderCatalogEntry,
  ProviderCategory,
  ProviderField,
  SelectOption,
} from "../data/provider-catalog";
import { fallbackProviderCatalog } from "../data/provider-fallback";
import { listProviderCatalog } from "../services/catalogs";
import {
  checkEngineHealth,
  listProviderModels,
  listProviderVoices,
  validateProvider,
} from "../services/providers";
import { useI18n } from "../composables/use-i18n";
import { formatHealthError, formatHealthMessage } from "../utils/health";
import { useSettingsStore } from "./settings";

export type ProviderStatus = "online" | "offline";

export type ProviderConfig = {
  apiKey?: string;
  baseUrl?: string;
  model?: string;
  voice?: string;
  extra?: Record<string, string>;
};

export type ProviderRuntime = {
  status: ProviderStatus;
  isValidating: boolean;
  lastError?: string;
  models: SelectOption[];
  voices: SelectOption[];
};

const configFieldIds = new Set(["apiKey", "baseUrl", "model", "voice"]);
const credentialFieldIds = new Set(["apiKey", "baseUrl"]);

export const useProvidersStore = defineStore("providers", () => {
  const settingsStore = useSettingsStore();
  const providerConfigs = useLocalStorage<Record<string, ProviderConfig>>(
    "whalewhisper/providers/configs",
    {}
  );
  const engineHealthSkipProviders = new Set(["alibaba-cloud-model-studio-speech"]);
  const providerRuntime = ref<Record<string, ProviderRuntime>>({});
  const catalogProviders = ref<ProviderCatalogEntry[]>([]);
  const catalogLoading = ref(false);
  const catalogError = ref<string | null>(null);
  const { t } = useI18n();

  const effectiveProviders = computed(() => {
    if (catalogProviders.value.length) return catalogProviders.value;
    if (catalogError.value) return fallbackProviderCatalog;
    return [];
  });

  const providerMetadata = computed<Record<string, ProviderCatalogEntry>>(() => {
    return effectiveProviders.value.reduce<Record<string, ProviderCatalogEntry>>((acc, option) => {
      acc[option.id] = option;
      return acc;
    }, {});
  });

  function resolveFieldScope(field: ProviderField) {
    if (field.scope === "config" && configFieldIds.has(field.id)) {
      return "config";
    }
    return "extra";
  }

  function resolveFieldDefault(field?: ProviderField) {
    if (!field || field.default === undefined || field.default === null) return "";
    return String(field.default);
  }

  function getProviderField(option: ProviderCatalogEntry | undefined, fieldId: string) {
    return option?.fields?.find((field) => field.id === fieldId);
  }

  function resolveProviderDefault(option: ProviderCatalogEntry | undefined, fieldId: string) {
    if (!option) return "";
    if (fieldId === "baseUrl") {
      return option.defaults?.baseUrl || resolveFieldDefault(getProviderField(option, fieldId));
    }
    if (fieldId === "model") {
      return option.defaults?.model || resolveFieldDefault(getProviderField(option, fieldId));
    }
    if (fieldId === "voice") {
      return option.defaults?.voice || resolveFieldDefault(getProviderField(option, fieldId));
    }
    return resolveFieldDefault(getProviderField(option, fieldId));
  }

  function getProviderMetadata(providerId: string) {
    return providerMetadata.value[providerId];
  }

  function buildDefaultExtra(option?: ProviderCatalogEntry) {
    const defaults: Record<string, string> = {};
    option?.fields?.forEach((field) => {
      if (resolveFieldScope(field) !== "extra") return;
      const defaultValue = resolveFieldDefault(field);
      if (defaultValue) {
        defaults[field.id] = defaultValue;
      }
    });
    return defaults;
  }

  function createDefaultConfig(option?: ProviderCatalogEntry): ProviderConfig {
    return {
      apiKey: resolveProviderDefault(option, "apiKey"),
      baseUrl: resolveProviderDefault(option, "baseUrl"),
      model: resolveProviderDefault(option, "model"),
      voice: resolveProviderDefault(option, "voice"),
      extra: buildDefaultExtra(option),
    };
  }

  function ensureProvider(providerId: string) {
    if (!providerId) return;
    const option = getProviderMetadata(providerId);
    if (!providerConfigs.value[providerId]) {
      providerConfigs.value = {
        ...providerConfigs.value,
        [providerId]: createDefaultConfig(option),
      };
    } else if (!providerConfigs.value[providerId].extra) {
      const current = providerConfigs.value[providerId];
      providerConfigs.value = {
        ...providerConfigs.value,
        [providerId]: {
          ...current,
          extra: buildDefaultExtra(option),
        },
      };
    }
    if (!providerRuntime.value[providerId]) {
      const modelField = getProviderField(option, "model");
      const voiceField = getProviderField(option, "voice");
      providerRuntime.value[providerId] = {
        status: "offline",
        isValidating: false,
        lastError: undefined,
        models: modelField?.options ?? [],
        voices: voiceField?.options ?? [],
      };
    }
  }

  function updateProviderConfig(providerId: string, patch: Partial<ProviderConfig>) {
    if (!providerId) return;
    ensureProvider(providerId);
    const current = providerConfigs.value[providerId];
    providerConfigs.value = {
      ...providerConfigs.value,
      [providerId]: {
        ...current,
        ...patch,
      },
    };
  }

  function getProviderConfig(providerId: string) {
    ensureProvider(providerId);
    return providerConfigs.value[providerId];
  }

  function getProviderExtra(providerId: string, key: string) {
    const config = getProviderConfig(providerId);
    return config.extra?.[key] ?? "";
  }

  function updateProviderExtra(providerId: string, key: string, value: string) {
    const config = getProviderConfig(providerId);
    updateProviderConfig(providerId, {
      extra: {
        ...(config.extra ?? {}),
        [key]: value,
      },
    });
  }

  function getProviderPayload(providerId: string) {
    const config = getProviderConfig(providerId);
    const payload: Record<string, string | Record<string, string>> = {
      id: providerId,
    };
    if (config.apiKey) {
      payload.apiKey = config.apiKey;
    }
    if (config.baseUrl) {
      payload.baseUrl = config.baseUrl;
    }
    if (config.model) {
      payload.model = config.model;
    }
    if (config.extra && Object.keys(config.extra).length) {
      const cleanedExtra = Object.entries(config.extra).reduce<Record<string, string>>(
        (acc, [key, value]) => {
          if (value && value.trim()) {
            acc[key] = value.trim();
          }
          return acc;
        },
        {}
      );
      if (Object.keys(cleanedExtra).length) {
        payload.extra = cleanedExtra;
      }
    }
    return payload;
  }

  function getProviderStatus(providerId: string) {
    ensureProvider(providerId);
    return providerRuntime.value[providerId]?.status ?? "offline";
  }

  function getProviderModels(providerId: string) {
    ensureProvider(providerId);
    return providerRuntime.value[providerId]?.models ?? [];
  }

  function getProviderVoices(providerId: string) {
    ensureProvider(providerId);
    return providerRuntime.value[providerId]?.voices ?? [];
  }

  function getProviderFields(providerId: string) {
    const option = getProviderMetadata(providerId);
    return option?.fields ?? [];
  }

  function getProviderFieldValue(providerId: string, field: ProviderField) {
    const config = getProviderConfig(providerId);
    const scope = resolveFieldScope(field);
    if (scope === "config" && configFieldIds.has(field.id)) {
      return (config as Record<string, string | undefined>)[field.id] ?? "";
    }
    return config.extra?.[field.id] ?? "";
  }

  function setProviderFieldValue(providerId: string, field: ProviderField, value: string) {
    const scope = resolveFieldScope(field);
    if (scope === "config" && configFieldIds.has(field.id)) {
      updateProviderConfig(providerId, { [field.id]: value } as Partial<ProviderConfig>);
      return;
    }
    updateProviderExtra(providerId, field.id, value);
  }

  function getProviderFieldOptions(providerId: string, field: ProviderField) {
    if (field.optionsSource === "models") {
      return getProviderModels(providerId);
    }
    if (field.optionsSource === "voices") {
      return getProviderVoices(providerId);
    }
    return field.options ?? [];
  }

  function normalizeBaseUrl(input?: string, fallback?: string) {
    const raw = (input || fallback || "").trim();
    if (!raw) return "";
    return raw.endsWith("/") ? raw : `${raw}/`;
  }

  function ensureDefaultConfig(providerId: string) {
    const option = getProviderMetadata(providerId);
    if (!option) return;
    const config = getProviderConfig(providerId);
    const patch: Partial<ProviderConfig> = {};

    const baseUrlDefault = resolveProviderDefault(option, "baseUrl");
    const modelDefault = resolveProviderDefault(option, "model");
    const voiceDefault = resolveProviderDefault(option, "voice");

    if (!config.baseUrl && baseUrlDefault) {
      patch.baseUrl = baseUrlDefault;
    }
    if (!config.model && modelDefault) {
      patch.model = modelDefault;
    }
    if (!config.voice && voiceDefault) {
      patch.voice = voiceDefault;
    }

    const extraDefaults = buildDefaultExtra(option);
    if (option.fields?.length) {
      const extraPatch: Record<string, string> = { ...(config.extra ?? {}) };
      option.fields.forEach((field) => {
        if (resolveFieldScope(field) !== "extra") return;
        if (!extraPatch[field.id] && extraDefaults[field.id]) {
          extraPatch[field.id] = extraDefaults[field.id];
        }
      });
      if (JSON.stringify(extraPatch) !== JSON.stringify(config.extra ?? {})) {
        patch.extra = extraPatch;
      }
    }

    if (Object.keys(patch).length) {
      updateProviderConfig(providerId, patch);
    }
  }

  function applyProviderDefaults(
    providerId: string,
    options: {
      forceBaseUrl?: boolean;
      forceModel?: boolean;
      forceVoice?: boolean;
    } = {}
  ) {
    if (!providerId) return;
    ensureProvider(providerId);
    const option = getProviderMetadata(providerId);
    const config = getProviderConfig(providerId);
    const patch: Partial<ProviderConfig> = {};

    const baseUrlDefault = resolveProviderDefault(option, "baseUrl");
    const modelDefault = resolveProviderDefault(option, "model");
    const voiceDefault = resolveProviderDefault(option, "voice");

    if (baseUrlDefault && (options.forceBaseUrl || !config.baseUrl)) {
      patch.baseUrl = baseUrlDefault;
    }
    if (modelDefault && (options.forceModel || !config.model)) {
      patch.model = modelDefault;
    }
    if (voiceDefault && (options.forceVoice || !config.voice)) {
      patch.voice = voiceDefault;
    }

    if (Object.keys(patch).length) {
      updateProviderConfig(providerId, patch);
    }
  }

  function resolveFieldValue(option: ProviderCatalogEntry, config: ProviderConfig, field: ProviderField) {
    const scope = resolveFieldScope(field);
    let value = "";
    if (scope === "config" && configFieldIds.has(field.id)) {
      value = (config as Record<string, string | undefined>)[field.id] ?? "";
    } else {
      value = config.extra?.[field.id] ?? "";
    }
    if (!value) {
      value = resolveFieldDefault(field);
    }
    return value;
  }

  function validateBasics(
    option: ProviderCatalogEntry | undefined,
    config: ProviderConfig,
    skipCredentials: boolean
  ) {
    if (!option?.fields?.length) {
      return { valid: true, reason: "" };
    }

    for (const field of option.fields) {
      if (!field.required) continue;
      if (skipCredentials && credentialFieldIds.has(field.id)) continue;
      const value = resolveFieldValue(option, config, field);
      if (!value.trim()) {
        return { valid: false, reason: `Missing ${field.label || field.id}.` };
      }
    }

    return { valid: true, reason: "" };
  }

  function isSelectedProvider(option: ProviderCatalogEntry | undefined, providerId: string) {
    if (!option) return false;
    if (option.category === "chat") return settingsStore.chatProviderId === providerId;
    if (option.category === "speech") return settingsStore.speechProviderId === providerId;
    return settingsStore.transcriptionProviderId === providerId;
  }

  async function fetchModels(option: ProviderCatalogEntry, config: ProviderConfig) {
    const modelField = getProviderField(option, "model");
    if (!modelField) return [];

    if (modelField.options?.length) {
      return modelField.options;
    }

    if (modelField.optionsSource !== "models") {
      return [];
    }

    const proxyModels = await listProviderModels(option, config);
    if (proxyModels) {
      return proxyModels;
    }

    const baseUrl = normalizeBaseUrl(config.baseUrl, resolveProviderDefault(option, "baseUrl"));
    if (!baseUrl) {
      throw new Error("Base URL is required.");
    }

    const modelsUrl = new URL("models", baseUrl).toString();
    const headers: Record<string, string> = {};
    if (config.apiKey) {
      headers.Authorization = `Bearer ${config.apiKey}`;
    }

    const response = await fetch(modelsUrl, { headers });
    if (!response.ok) {
      throw new Error(`Model list request failed: ${response.status}`);
    }

    const data = await response.json();
    const list = Array.isArray(data?.data) ? data.data : [];
    return list.map((item: { id?: string }) => ({
      id: item.id ?? "unknown",
      label: item.id ?? "Unknown",
    }));
  }

  async function fetchVoices(option: ProviderCatalogEntry, config: ProviderConfig) {
    const voiceField = getProviderField(option, "voice");
    if (!voiceField) return [];

    if (voiceField.options?.length) {
      return voiceField.options;
    }

    if (voiceField.optionsSource !== "voices") {
      return [];
    }

    const proxyVoices = await listProviderVoices(option, config);
    if (proxyVoices) {
      return proxyVoices;
    }

    return [];
  }

  async function refreshProvider(providerId: string) {
    if (!providerId) return false;
    ensureProvider(providerId);
    ensureDefaultConfig(providerId);

    const option = getProviderMetadata(providerId);
    const config = getProviderConfig(providerId);
    const runtime = providerRuntime.value[providerId];
    const engineId = option?.engineId;
    const usesEngineHealth = Boolean(
      engineId &&
        option?.category &&
        isSelectedProvider(option, providerId) &&
        !engineHealthSkipProviders.has(providerId)
    );

    runtime.isValidating = true;
    runtime.lastError = undefined;

    const basic = validateBasics(option, config, usesEngineHealth);
    if (!basic.valid) {
      runtime.status = "offline";
      runtime.lastError = basic.reason;
      runtime.models = getProviderField(option, "model")?.options ?? [];
      runtime.voices = getProviderField(option, "voice")?.options ?? [];
      runtime.isValidating = false;
      return false;
    }

    runtime.status = "online";

    if (option) {
      if (usesEngineHealth && engineId) {
        try {
          const health = await checkEngineHealth(option.category, engineId, config);
          if (!health.ok) {
            runtime.status = "offline";
            runtime.lastError = formatHealthMessage(health, t) || t("health.failed", "Health check failed.");
            runtime.isValidating = false;
            return false;
          }
        } catch (error) {
          runtime.status = "offline";
          runtime.lastError = formatHealthError(error, t);
          runtime.isValidating = false;
          return false;
        }
      } else {
        try {
          const validation = await validateProvider(option, config);
          if (!validation.valid) {
            runtime.status = "offline";
            runtime.lastError = validation.reason || "Provider validation failed.";
            runtime.isValidating = false;
            return false;
          }
        } catch (error) {
          runtime.status = "offline";
          runtime.lastError =
            error instanceof Error ? error.message : "Provider validation failed.";
          runtime.isValidating = false;
          return false;
        }
      }
    }

    if (option) {
      try {
        runtime.models = await fetchModels(option, config);
      } catch (error) {
        runtime.models = getProviderField(option, "model")?.options ?? [];
        if (!usesEngineHealth) {
          runtime.status = "offline";
          runtime.lastError = error instanceof Error ? error.message : "Model list fetch failed.";
        }
      }

      try {
        runtime.voices = await fetchVoices(option, config);
      } catch {
        runtime.voices = getProviderField(option, "voice")?.options ?? [];
      }
    }

    runtime.isValidating = false;
    return runtime.status === "online";
  }

  const pendingRefreshIds = new Set<string>();
  const flushRefreshQueue = useDebounceFn(() => {
    pendingRefreshIds.forEach((providerId) => {
      void refreshProvider(providerId);
    });
    pendingRefreshIds.clear();
  }, 600);

  watch(
    providerConfigs,
    (next, prev) => {
      const nextKeys = Object.keys(next ?? {});
      const prevKeys = Object.keys(prev ?? {});
      const allKeys = new Set([...nextKeys, ...prevKeys]);
      allKeys.forEach((key) => {
        const nextConfig = next?.[key];
        const prevConfig = prev?.[key];
        if (JSON.stringify(nextConfig) !== JSON.stringify(prevConfig)) {
          pendingRefreshIds.add(key);
        }
      });
      flushRefreshQueue();
    },
    { deep: true }
  );

  async function refreshCatalog() {
    catalogLoading.value = true;
    catalogError.value = null;
    try {
      const list = await listProviderCatalog();
      catalogProviders.value = list;
    } catch (error) {
      catalogError.value = error instanceof Error ? error.message : "Failed to load catalog.";
      if (!catalogProviders.value.length) {
        catalogProviders.value = fallbackProviderCatalog;
      }
    } finally {
      catalogLoading.value = false;
    }

    effectiveProviders.value.forEach((option) => {
      ensureProvider(option.id);
      ensureDefaultConfig(option.id);
    });
  }

  function getProviderOptions(category: ProviderCategory) {
    return effectiveProviders.value.filter((provider) => provider.category === category);
  }

  fallbackProviderCatalog.forEach((option) => {
    ensureProvider(option.id);
    ensureDefaultConfig(option.id);
  });

  void refreshCatalog();

  return {
    providerConfigs,
    providerRuntime,
    catalogProviders,
    catalogLoading,
    catalogError,
    getProviderOptions,
    getProviderMetadata,
    getProviderConfig,
    getProviderExtra,
    updateProviderConfig,
    updateProviderExtra,
    getProviderPayload,
    getProviderStatus,
    getProviderModels,
    getProviderVoices,
    getProviderFields,
    getProviderFieldValue,
    setProviderFieldValue,
    getProviderFieldOptions,
    refreshProvider,
    refreshCatalog,
    applyProviderDefaults,
  };
});
