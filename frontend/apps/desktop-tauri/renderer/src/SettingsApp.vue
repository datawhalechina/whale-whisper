<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";

import { SettingsLayout } from "@whalewhisper/stage-settings-ui";
import { useI18n } from "@whalewhisper/app-core/composables/use-i18n";
import { useLive2dRuntime } from "@whalewhisper/app-core/stores/live2d-runtime";
import { useTranscriptionStore } from "@whalewhisper/app-core/stores/transcription";
import { closeSettingsWindow } from "./services/desktop";
import { listenDesktopActionToken } from "./services/desktop";
import {
  AppearanceSection,
  ChatSection,
  PersonaSection,
  MemorySection,
  AudioSection,
  ModelSection,
  AgentSection,
  StageViewSection,
  SystemSection,
} from "@whalewhisper/app-settings";

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
const dialogRef = ref<HTMLDivElement | null>(null);
let dragHandleEl: HTMLElement | null = null;
let hoverTimer: number | null = null;
let ignoreApplied: boolean | null = null;
let isPolling = false;
let unlistenActionToken: null | (() => void) = null;
const dragIgnoreSelectors =
  "button, a, input, textarea, select, option, label, [contenteditable='true'], [role='button'], [role='link'], [role='slider'], [role='checkbox'], [role='switch'], [role='textbox'], [data-tauri-drag-region='false'], [data-drag-ignore='true']";
const live2dRuntime = useLive2dRuntime();
const transcriptionStore = useTranscriptionStore();

function stopSettingsTestMic() {
  if (transcriptionStore.listeningSource !== "settings-test") return;
  void transcriptionStore.stopListening();
}

function isTauriRuntime() {
  if (typeof window === "undefined") return false;
  return Boolean((window as Window & { __TAURI_INTERNALS__?: any }).__TAURI_INTERNALS__);
}

async function handleDragPointerDown(event: PointerEvent) {
  if (event.button !== 0) return;
  const path = event.composedPath?.() ?? [];
  if (
    path.some(
      (node) => node instanceof Element && node.closest(dragIgnoreSelectors)
    )
  ) {
    return;
  }
  const target = event.target as HTMLElement | null;
  if (target?.closest(dragIgnoreSelectors)) return;
  if (!isTauriRuntime()) return;
  const { getCurrentWindow } = await import("@tauri-apps/api/window");
  await getCurrentWindow().startDragging();
}

async function pollCursorHover() {
  if (isPolling) return;
  isPolling = true;
  try {
    if (!isTauriRuntime()) return;
    const { getCurrentWindow, cursorPosition } = await import("@tauri-apps/api/window");
    const window = getCurrentWindow();
    const [position, scale, cursor] = await Promise.all([
      window.innerPosition(),
      window.scaleFactor(),
      cursorPosition(),
    ]);
    const rect = dialogRef.value?.getBoundingClientRect();
    if (!rect) return;
    const localX = (cursor.x - position.x) / scale;
    const localY = (cursor.y - position.y) / scale;
    const inside =
      localX >= rect.left &&
      localX <= rect.right &&
      localY >= rect.top &&
      localY <= rect.bottom;
    const nextIgnore = !inside;
    if (ignoreApplied !== nextIgnore) {
      await window.setIgnoreCursorEvents(nextIgnore);
      ignoreApplied = nextIgnore;
    }
  } finally {
    isPolling = false;
  }
}

async function handleClose() {
  stopSettingsTestMic();
  await closeSettingsWindow();
}

function handleVisibilityChange() {
  if (document.visibilityState === "hidden") {
    stopSettingsTestMic();
  }
}

onMounted(() => {
  dragHandleEl =
    dialogRef.value?.querySelector<HTMLElement>("[data-settings-drag-handle]") ?? null;
  dragHandleEl?.addEventListener("pointerdown", handleDragPointerDown);
  listenDesktopActionToken((payload) => {
    void live2dRuntime.applySpecialToken(payload.token);
  }).then((unlisten) => {
    unlistenActionToken = unlisten ?? null;
  });
  if (isTauriRuntime()) {
    hoverTimer = window.setInterval(() => {
      void pollCursorHover();
    }, 60);
  }
  document.addEventListener("visibilitychange", handleVisibilityChange);
});

onUnmounted(() => {
  stopSettingsTestMic();
  dragHandleEl?.removeEventListener("pointerdown", handleDragPointerDown);
  if (unlistenActionToken) {
    unlistenActionToken();
    unlistenActionToken = null;
  }
  if (hoverTimer) {
    window.clearInterval(hoverTimer);
    hoverTimer = null;
  }
  document.removeEventListener("visibilitychange", handleVisibilityChange);
  dragHandleEl = null;
});
</script>

<template>
  <div class="relative min-h-full w-full text-neutral-900">
    <div class="relative z-10 flex min-h-full w-full items-center justify-center p-6">
      <div ref="dialogRef" class="w-full max-w-4xl">
        <SettingsLayout
          v-model:activeTab="activeTab"
          :title="t('settings.title')"
          :subtitle="t('settings.subtitle')"
          :tabs="tabs"
          :container-class="[dialogSizeClass, dialogPaddingClass, 'w-full']"
          :on-close="handleClose"
        />
      </div>
    </div>
  </div>
</template>
