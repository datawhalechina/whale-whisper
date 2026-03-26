<script setup lang="ts">
import { storeToRefs } from "pinia";
import { computed, watch } from "vue";

import { ModelSection } from "@whalewhisper/stage-settings-ui";
import { useI18n } from "@whalewhisper/app-core/composables/use-i18n";
import { useProvidersStore } from "@whalewhisper/app-core/stores/providers";
import { useSettingsStore } from "@whalewhisper/app-core/stores/settings";

const settingsStore = useSettingsStore();
const providersStore = useProvidersStore();
const { t, locale } = useI18n();
const localeValue = computed(() => locale.value || "en");

const { chatProviderId, speechProviderId, transcriptionProviderId } = storeToRefs(settingsStore);
const { catalogError, catalogLoading } = storeToRefs(providersStore);

const chatOptions = computed(() => providersStore.getProviderOptions("chat"));
const speechOptions = computed(() => providersStore.getProviderOptions("speech"));
const transcriptionOptions = computed(() => providersStore.getProviderOptions("transcription"));

watch(
  chatOptions,
  (options) => {
    if (!options.length) return;
    if (!options.find((option) => option.id === chatProviderId.value)) {
      chatProviderId.value = options[0].id;
    }
  },
  { immediate: true }
);

watch(
  speechOptions,
  (options) => {
    if (!options.length) return;
    if (!options.find((option) => option.id === speechProviderId.value)) {
      speechProviderId.value = options[0].id;
    }
  },
  { immediate: true }
);

watch(
  transcriptionOptions,
  (options) => {
    if (!options.length) return;
    if (!options.find((option) => option.id === transcriptionProviderId.value)) {
      transcriptionProviderId.value = options[0].id;
    }
  },
  { immediate: true }
);

watch(
  chatProviderId,
  (providerId) => {
    if (!providerId) return;
    providersStore.applyProviderDefaults(providerId, { forceBaseUrl: true });
    void providersStore.refreshProvider(providerId);
  },
  { immediate: true, flush: "post" }
);

watch(
  speechProviderId,
  (providerId) => {
    if (!providerId) return;
    providersStore.applyProviderDefaults(providerId, { forceBaseUrl: true });
    void providersStore.refreshProvider(providerId);
  },
  { immediate: true, flush: "post" }
);

watch(
  transcriptionProviderId,
  (providerId) => {
    if (!providerId) return;
    providersStore.applyProviderDefaults(providerId, { forceBaseUrl: true });
    void providersStore.refreshProvider(providerId);
  },
  { immediate: true, flush: "post" }
);

function buildPanel(category: "chat" | "speech" | "transcription", providerId: string, title: string, description: string) {
  const fields = providersStore.getProviderFields(providerId).map((field) => ({
    id: field.id,
    label: field.label,
    description: field.description,
    required: field.required,
    type: field.type,
    placeholder: field.placeholder,
    value: providersStore.getProviderFieldValue(providerId, field),
    options: providersStore.getProviderFieldOptions(providerId, field),
  }));

  return {
    id: category,
    title,
    description,
    modelValue: providerId,
    options: providersStore.getProviderOptions(category),
    status: providersStore.getProviderStatus(providerId),
    runtime: providersStore.providerRuntime[providerId],
    fields,
    onUpdateModelValue: (value: string) => {
      if (category === "chat") {
        chatProviderId.value = value;
      } else if (category === "speech") {
        speechProviderId.value = value;
      } else {
        transcriptionProviderId.value = value;
      }
    },
    onRefresh: () => {
      void providersStore.refreshProvider(providerId);
    },
    onUpdateFieldValue: (fieldId: string, value: string) => {
      const updatedProviderId =
        category === "chat"
          ? chatProviderId.value
          : category === "speech"
            ? speechProviderId.value
            : transcriptionProviderId.value;
      const providerFields = providersStore.getProviderFields(updatedProviderId);
      const targetField = providerFields.find((field) => field.id === fieldId);
      if (!targetField) return;
      providersStore.setProviderFieldValue(updatedProviderId, targetField, value);
      if (category === "speech" && fieldId === "model") {
        const voiceField = providerFields.find((field) => field.id === "voice");
        if (voiceField) {
          providersStore.setProviderFieldValue(updatedProviderId, voiceField, "");
        }
        void providersStore.refreshProvider(updatedProviderId);
      }
    },
  };
}

const panels = computed(() => [
  buildPanel("chat", chatProviderId.value, t("providers.chat.title"), t("providers.chat.desc")),
  buildPanel(
    "transcription",
    transcriptionProviderId.value,
    t("providers.transcription.title"),
    t("providers.transcription.desc")
  ),
  buildPanel(
    "speech",
    speechProviderId.value,
    t("providers.speech.title"),
    t("providers.speech.desc")
  ),
]);
</script>

<template>
  <ModelSection
    :locale="localeValue"
    :t="t"
    :catalog-error="catalogError"
    :catalog-loading="catalogLoading"
    :panels="panels"
  />
</template>
