import { useLocalStorage } from "@vueuse/core";
import { defineStore, storeToRefs } from "pinia";
import { ref } from "vue";

import { useStageSettingsStore } from "@whalewhisper/stage-core";

export const useSettingsStore = defineStore("settings", () => {
  const stageSettings = useStageSettingsStore();
  const {
    stageModelRenderer,
    stageViewControlsEnabled,
    stageDragEnabled,
    stageActionTokensEnabled,
    stageActionTokensPrompt,
  } = storeToRefs(stageSettings);
  const themeColorsHueDynamic = ref(false);
  const chatProviderId = useLocalStorage("whalewhisper/providers/chat", "openrouter-ai");
  const speechProviderId = useLocalStorage("whalewhisper/providers/speech", "browser-local-audio-speech");
  const transcriptionProviderId = useLocalStorage(
    "whalewhisper/providers/transcription",
    "openai-audio-transcription"
  );

  return {
    stageModelRenderer,
    stageViewControlsEnabled,
    stageDragEnabled,
    stageActionTokensEnabled,
    stageActionTokensPrompt,
    themeColorsHueDynamic,
    chatProviderId,
    speechProviderId,
    transcriptionProviderId,
    toggleViewControls: stageSettings.toggleViewControls,
  };
});
