<script setup lang="ts">
import { computed } from "vue";

import SelectMenu from "./ui/SelectMenu.vue";

type ProviderOption = {
  id: string;
  label: string;
  description?: string;
  icon?: string;
};

type ProviderField = {
  id: string;
  label: string;
  description?: string;
  required?: boolean;
  type?: string;
  placeholder?: string;
  value?: string;
  options?: ProviderOption[];
};

type ProviderRuntime = {
  isValidating?: boolean;
  lastError?: string;
};

type ProviderStatus = "online" | "offline" | "unknown";

const props = defineProps<{
  title: string;
  description: string;
  modelValue: string;
  options: ProviderOption[];
  status?: ProviderStatus;
  runtime?: ProviderRuntime;
  fields?: ProviderField[];
  locale?: string;
  t?: (key: string) => string;
  onRefresh?: () => void;
  onUpdateModelValue?: (value: string) => void;
  onUpdateFieldValue?: (fieldId: string, value: string) => void;
}>();

const resolvedLocale = computed(() => {
  if (props.locale) return props.locale;
  if (typeof navigator !== "undefined" && navigator.language) {
    return navigator.language;
  }
  return "en";
});
const isZh = computed(() => resolvedLocale.value.toLowerCase().startsWith("zh"));

const fallbackEn = {
  "providers.status.label": "Status",
  "providers.placeholder.provider": "Choose provider",
  "providers.placeholder.model": "Choose model",
  "providers.placeholder.voice": "Choose voice",
  "providers.label.apiKey": "API Key",
  "providers.label.baseUrl": "Base URL",
  "providers.label.model": "Model",
  "providers.label.voice": "Voice",
  "common.check": "Check",
  "common.checking": "Checking",
  "common.online": "Online",
  "common.offline": "Offline",
  "common.select": "Select",
};

const fallbackZh = {
  "providers.status.label": "状态",
  "providers.placeholder.provider": "选择渠道",
  "providers.placeholder.model": "选择模型",
  "providers.placeholder.voice": "选择音色",
  "providers.label.apiKey": "API Key",
  "providers.label.baseUrl": "Base URL",
  "providers.label.model": "模型",
  "providers.label.voice": "音色",
  "common.check": "检查",
  "common.checking": "检查中",
  "common.online": "在线",
  "common.offline": "离线",
  "common.select": "请选择",
};

const fallbackText = computed(() => (isZh.value ? fallbackZh : fallbackEn));
const t = (key: string) => {
  if (props.t) {
    const resolved = props.t(key);
    if (resolved && resolved !== key) return resolved;
  }
  return fallbackText.value[key as keyof typeof fallbackEn] ?? key;
};

const providerId = computed({
  get: () => props.modelValue,
  set: (value: string) => props.onUpdateModelValue?.(value),
});

const labelOverrides = computed(() => ({
  apiKey: t("providers.label.apiKey"),
  baseUrl: t("providers.label.baseUrl"),
  model: t("providers.label.model"),
  voice: t("providers.label.voice"),
}));

const options = computed(() => props.options ?? []);
const fields = computed(() => props.fields ?? []);
const status = computed(() => props.status ?? "unknown");

const statusText = computed(() => {
  if (props.runtime?.isValidating) {
    return t("common.checking");
  }
  return status.value === "online" ? t("common.online") : t("common.offline");
});

function resolveLabel(field: ProviderField) {
  return labelOverrides.value[field.id as keyof typeof labelOverrides.value] ?? field.label;
}

function resolvePlaceholder(field: ProviderField) {
  if (field.placeholder) return field.placeholder;
  if (field.id === "apiKey") return "sk-...";
  if (
    field.id === "voice" &&
    field.type === "select" &&
    (field.options?.length ?? 0) === 0
  ) {
    return isZh.value ? "没有支持的声线" : "No compatible voices";
  }
  if (field.id === "model") return t("providers.placeholder.model");
  if (field.id === "voice") return t("providers.placeholder.voice");
  return field.label || t("common.select");
}

function getInputType(field: ProviderField) {
  return field.type === "secret" ? "password" : "text";
}
</script>

<template>
  <div class="min-w-0 rounded-2xl border border-neutral-200/70 bg-white/70 p-4 shadow-sm dark:border-neutral-800/70 dark:bg-neutral-950/60">
    <div class="mb-3 text-sm font-semibold text-neutral-800 dark:text-neutral-100">
      {{ props.title }}
    </div>
    <div class="text-xs text-neutral-500 dark:text-neutral-400">
      {{ props.description }}
    </div>
    <div class="mt-3 flex items-center justify-between rounded-xl border border-neutral-200/70 bg-white/60 px-3 py-2 text-xs text-neutral-500 dark:border-neutral-800/70 dark:bg-neutral-900/60 dark:text-neutral-400">
      <div class="flex items-center gap-2">
        <span>{{ t("providers.status.label") }}</span>
        <span class="font-medium text-neutral-700 dark:text-neutral-200">
          {{ statusText }}
        </span>
      </div>
      <button
        type="button"
        class="rounded-lg border border-neutral-200 bg-white/80 px-3 py-1 text-xs text-neutral-600 transition hover:text-neutral-900 disabled:opacity-60 dark:border-neutral-700 dark:bg-neutral-800/80 dark:text-neutral-300"
        :disabled="props.runtime?.isValidating"
        @click="props.onRefresh?.()"
      >
        {{ t("common.check") }}
      </button>
    </div>
    <div class="mt-3">
      <SelectMenu
        v-model="providerId"
        :options="options"
        :status="status"
        :placeholder="t('providers.placeholder.provider')"
      />
    </div>
    <div class="mt-3 grid gap-2">
      <div v-for="field in fields" :key="field.id" class="grid min-w-0 gap-1">
        <label class="text-xs text-neutral-500 dark:text-neutral-400">
          {{ resolveLabel(field) }}
          <span v-if="field.required" class="text-rose-500"> *</span>
        </label>
        <SelectMenu
          v-if="field.type === 'select' && (field.options?.length ?? 0) > 0"
          :model-value="field.value ?? ''"
          :options="field.options ?? []"
          :placeholder="resolvePlaceholder(field)"
          @update:modelValue="(value) => props.onUpdateFieldValue?.(field.id, value)"
        />
        <input
          v-else
          :value="field.value ?? ''"
          :type="getInputType(field)"
          :placeholder="resolvePlaceholder(field)"
          class="w-full min-w-0 rounded-lg border border-neutral-200 bg-white/80 px-3 py-2 text-sm text-neutral-700 shadow-sm outline-none transition focus:border-primary-400 dark:border-neutral-800 dark:bg-neutral-900/70 dark:text-neutral-200"
          @input="props.onUpdateFieldValue?.(field.id, ($event.target as HTMLInputElement).value)"
        />
        <div v-if="field.description" class="text-xs text-neutral-400 dark:text-neutral-500">
          {{ field.description }}
        </div>
      </div>
      <div
        v-if="props.runtime?.lastError"
        class="max-w-full break-all rounded-lg border border-rose-200/60 bg-rose-50/70 px-3 py-2 text-xs text-rose-500 dark:border-rose-500/30 dark:bg-rose-950/40"
      >
        {{ props.runtime.lastError }}
      </div>
    </div>
  </div>
</template>
