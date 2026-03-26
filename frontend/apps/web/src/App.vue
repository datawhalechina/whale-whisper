<script setup lang="ts">
import { storeToRefs } from "pinia";
import { computed, onMounted, onUnmounted, ref } from "vue";

import { breakpointsTailwind, useBreakpoints, useMouse } from "@vueuse/core";

import { BackgroundProvider } from "@whalewhisper/app-settings/backgrounds";
import Header from "./components/layouts/Header.vue";
import InteractiveArea from "./components/layouts/InteractiveArea.vue";
import MobileHeader from "./components/layouts/MobileHeader.vue";
import MobileInteractiveArea from "./components/layouts/MobileInteractiveArea.vue";
import ConversationSidebar from "./components/layouts/ConversationSidebar.vue";
import SettingsDialog from "./components/settings/SettingsDialog.vue";
import WidgetStage from "./components/scenes/WidgetStage.vue";
import { useBackgroundThemeColor } from "@whalewhisper/app-core/composables/theme-color";
import { provideStageI18n } from "@whalewhisper/stage-core";
import { useActionTokenPromptSync } from "@whalewhisper/app-core/composables/use-action-token-prompt-sync";
import { useI18n } from "@whalewhisper/app-core/composables/use-i18n";
import { useBackgroundStore } from "@whalewhisper/app-core/stores/background";
import { useChatStore } from "@whalewhisper/app-core/stores/chat";
import { useLive2d } from "@whalewhisper/app-core/stores/live2d";
import { useLive2dRuntime } from "@whalewhisper/app-core/stores/live2d-runtime";
import { useSpeechOutputStore } from "@whalewhisper/app-core/stores/speech-output";
import { useUiStore } from "@whalewhisper/app-core/stores/ui";

const uiStore = useUiStore();
const { settingsOpen, sessionsOpen } = storeToRefs(uiStore);
const mobileOverlayOpen = ref(false);
const paused = computed(() => settingsOpen.value || mobileOverlayOpen.value);
const { t } = useI18n();
provideStageI18n({ t });

function handleSettingsOpen(open: boolean) {
  mobileOverlayOpen.value = open;
}

const positionCursor = useMouse();
const { scale, position, positionInPercentageString } = storeToRefs(useLive2d());
const breakpoints = useBreakpoints(breakpointsTailwind);
const isMobile = breakpoints.smaller("md");

const backgroundStore = useBackgroundStore();
const { selectedOption, sampledColor, options } = storeToRefs(backgroundStore);
const backgroundOption = computed(() => selectedOption.value ?? options.value[0]);
const backgroundSurface = ref<InstanceType<typeof BackgroundProvider> | null>(null);

const { syncBackgroundTheme } = useBackgroundThemeColor({
  backgroundSurface,
  selectedOption,
  sampledColor,
});

useActionTokenPromptSync();

const chatStore = useChatStore();
const live2dRuntime = useLive2dRuntime();
const speechOutput = useSpeechOutputStore();
let disposeTokenLiteral: (() => void) | null = null;
let disposeSpecialToken: (() => void) | null = null;
let disposeSpeechOutput: (() => void) | null = null;

const stageXOffset = computed(() => {
  const base = position.value.x;
  return `${isMobile.value ? base : base - 10}%`;
});

onMounted(() => {
  syncBackgroundTheme();
  const openTarget = new URLSearchParams(window.location.search).get("open");
  if (openTarget === "settings") {
    uiStore.openSettings();
  }
  if (openTarget === "sessions") {
    uiStore.openSessions();
  }
  chatStore.connect();
  disposeTokenLiteral = chatStore.onTokenLiteral(async (literal) => {
    speechOutput.pushAssistantLiteral(literal);
  });
  disposeSpecialToken = chatStore.onTokenSpecial(async (special) => {
    await live2dRuntime.applySpecialToken(special);
    speechOutput.pushAssistantSpecial(special);
  });
  disposeSpeechOutput = chatStore.onAssistantFinal(async (message) => {
    await speechOutput.endAssistantStream(message.content);
  });
});

onUnmounted(() => {
  disposeTokenLiteral?.();
  disposeSpecialToken?.();
  disposeSpeechOutput?.();
});
</script>

<template>
  <BackgroundProvider
    ref="backgroundSurface"
    class="widgets top-widgets"
    :background="backgroundOption"
    :top-color="sampledColor"
  >
    <SettingsDialog />
    <div relative flex="~ col" z-2 h-100dvh w-100vw of-hidden>
      <div class="px-0 py-1 md:px-3 md:py-3" w-full gap-2>
        <Header v-if="!isMobile" />
        <MobileHeader v-else />
      </div>
      <ConversationSidebar v-if="!isMobile || sessionsOpen" />
      <button
        v-if="!isMobile"
        class="absolute bottom-8 left-4 z-40 flex items-center gap-2 rounded-full px-4 py-2 text-xs text-neutral-600 shadow-lg transition hover:text-neutral-900 dark:text-neutral-300 dark:hover:text-neutral-100"
        border="2 solid neutral-100/60 dark:neutral-800/30"
        bg="neutral-50/80 dark:neutral-800/80"
        backdrop-blur-md
        type="button"
        :title="t('sessions.toggle')"
        @click="uiStore.toggleSessions()"
      >
        <div i-solar:chat-round-line-bold size-4 />
        <span>{{ t("sessions.toggle") }}</span>
      </button>
      <div relative flex="~ 1 row gap-y-0 gap-x-2 <md:col">
        <WidgetStage
          flex-1
          min-w="1/2"
          :paused="paused"
          :focus-at="{
            x: positionCursor.x.value,
            y: positionCursor.y.value,
          }"
          :x-offset="stageXOffset"
          :y-offset="positionInPercentageString.y"
          :scale="scale"
        />
        <InteractiveArea v-if="!isMobile" />
        <MobileInteractiveArea v-if="isMobile" @settings-open="handleSettingsOpen" />
      </div>
    </div>
  </BackgroundProvider>
</template>
