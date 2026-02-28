<script setup lang="ts">
import { storeToRefs } from "pinia";
import { computed, ref } from "vue";
import { useI18n } from "@whalewhisper/app-core/composables/use-i18n";
import { useTranscriptionStore } from "@whalewhisper/app-core/stores/transcription";
import { useUiStore } from "@whalewhisper/app-core/stores/ui";
import { SettingsLayout } from "@whalewhisper/stage-settings-ui";
import LanguageSelect from "../layouts/LanguageSelect.vue";
import {
  AppearanceSection,
  AudioSection,
  AgentSection,
  ChatSection,
  MemorySection,
  ModelSection,
  PersonaSection,
  StageViewSection,
  SystemSection,
} from "@whalewhisper/app-settings";

const uiStore = useUiStore();
const { settingsOpen } = storeToRefs(uiStore);
const transcriptionStore = useTranscriptionStore();
const { t } = useI18n();
const tabs = computed(() => [
  { id: "appearance", label: t("settings.tabs.appearance"), component: AppearanceSection },
  { id: "chat", label: t("settings.tabs.chat"), component: ChatSection },
  { id: "persona", label: t("settings.tabs.persona"), component: PersonaSection },
  { id: "memory", label: t("settings.tabs.memory"), component: MemorySection },
  { id: "audio", label: t("settings.tabs.audio"), component: AudioSection },
  { id: "model", label: t("settings.tabs.providers"), component: ModelSection },
  { id: "agent", label: t("settings.tabs.agent"), component: AgentSection },
  { id: "stage", label: t("settings.tabs.stageModels"), component: StageViewSection },
  { id: "system", label: t("settings.tabs.system"), component: SystemSection },
]);
const activeTab = ref("appearance");
const dialogSizeClass = computed(() =>
  activeTab.value === "stage" ? "max-h-[98vh]" : "max-h-[90vh]"
);
const dialogPaddingClass = computed(() =>
  activeTab.value === "stage" ? "p-4" : "p-6"
);

function handleClose() {
  if (transcriptionStore.listeningSource === "settings-test") {
    void transcriptionStore.stopListening();
  }
  uiStore.closeSettings();
}
</script>

<template>
  <div v-if="settingsOpen" class="fixed inset-0 z-50 flex items-center justify-center p-4">
    <button
      class="absolute inset-0 bg-black/40 backdrop-blur-sm"
      type="button"
      :aria-label="t('aria.closeSettings')"
      @click="handleClose"
    />
    <SettingsLayout
      v-model:activeTab="activeTab"
      :title="t('settings.title')"
      :subtitle="t('settings.subtitle')"
      :tabs="tabs"
      :container-class="[dialogSizeClass, dialogPaddingClass, 'max-w-4xl']"
      :on-close="handleClose"
    >
      <template #headerExtra>
        <div class="md:hidden">
          <LanguageSelect size-class="w-24" list-class="max-h-[180px]" item-class="min-h-[48px]" />
        </div>
      </template>
    </SettingsLayout>
  </div>
</template>
