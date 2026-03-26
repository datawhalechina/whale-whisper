<script setup lang="ts">
import { computed, onUnmounted } from "vue";

import { AudioSection } from "@whalewhisper/stage-settings-ui";
import { useI18n } from "@whalewhisper/app-core/composables/use-i18n";
import { useHearingStore } from "@whalewhisper/app-core/stores/hearing";
import { useSpeechOutputStore } from "@whalewhisper/app-core/stores/speech-output";
import { useTranscriptionStore } from "@whalewhisper/app-core/stores/transcription";

const hearingStore = useHearingStore();
const transcriptionStore = useTranscriptionStore();
const speechOutputStore = useSpeechOutputStore();
const { t, locale } = useI18n();
const localeValue = computed(() => locale.value || "en");

onUnmounted(() => {
  if (transcriptionStore.listeningSource !== "settings-test") return;
  void transcriptionStore.stopListening();
});
</script>

<template>
  <AudioSection
    :locale="localeValue"
    :t="t"
    :hearing="hearingStore"
    :transcription="transcriptionStore"
    :speech-output="speechOutputStore"
  />
</template>
