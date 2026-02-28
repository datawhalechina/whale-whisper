<script setup lang="ts">
import { computed, ref } from "vue";
import { storeToRefs } from "pinia";

import { useI18n } from "@whalewhisper/app-core/composables/use-i18n";
import { useChatStore } from "@whalewhisper/app-core/stores/chat";
import { useSettingsStore } from "@whalewhisper/app-core/stores/settings";
import { useTranscriptionStore } from "@whalewhisper/app-core/stores/transcription";
import BasicTextarea from "../ui/BasicTextarea.vue";

const props = withDefaults(
  defineProps<{
    variant?: "desktop" | "mobile";
    submitOnEnter?: boolean;
  }>(),
  {
    variant: "desktop",
  }
);

const messageInput = ref("");
const isComposing = ref(false);

const chatStore = useChatStore();
const transcriptionStore = useTranscriptionStore();
const { t } = useI18n();
const { themeColorsHueDynamic } = storeToRefs(useSettingsStore());
const {
  listening: transcriptionListening,
  listeningSource: transcriptionListeningSource,
  canListen: canListenToTranscription,
  error: transcriptionError,
} = storeToRefs(transcriptionStore);
const isMobile = computed(() => props.variant === "mobile");
const submitOnEnter = computed(() =>
  typeof props.submitOnEnter === "boolean"
    ? props.submitOnEnter
    : !isMobile.value
);
const showSendButton = computed(
  () => Boolean(messageInput.value.trim()) || isComposing.value
);
const chatMicActive = computed(
  () =>
    transcriptionListening.value &&
    transcriptionListeningSource.value === "chat-input"
);
const chatMicButtonTitle = computed(() =>
  chatMicActive.value ? t("audio.stt.stop") : t("audio.stt.start")
);
const showChatMicError = computed(
  () =>
    Boolean(transcriptionError.value) &&
    transcriptionListeningSource.value === "chat-input"
);

function handleSend() {
  if (!messageInput.value.trim() || isComposing.value) {
    return;
  }

  chatStore.send(messageInput.value);
  messageInput.value = "";
}

function toggleChatMic() {
  if (!canListenToTranscription.value) return;
  transcriptionStore.enabled = true;
  if (chatMicActive.value) {
    void transcriptionStore.stopListening();
    return;
  }
  void transcriptionStore.startListening({
    autoSend: true,
    source: "chat-input",
  });
}
</script>

<template>
  <div v-if="isMobile" class="ph-no-capture w-full">
    <div class="flex w-full items-end gap-1">
      <button
        type="button"
        class="mb-0.5 flex h-8 w-8 items-center justify-center rounded-full border border-neutral-200/70 bg-white/70 text-neutral-500 shadow-sm backdrop-blur-md transition hover:text-neutral-800 disabled:cursor-not-allowed disabled:opacity-40 dark:border-neutral-700/70 dark:bg-neutral-900/70 dark:text-neutral-200 dark:hover:text-neutral-50"
        :class="chatMicActive
          ? 'border-primary-300/80 bg-primary-100/80 text-primary-600 dark:border-primary-300/70 dark:bg-primary-500/20 dark:text-primary-100'
          : ''"
        :title="chatMicButtonTitle"
        :disabled="!canListenToTranscription"
        @click="toggleChatMic"
      >
        <div :class="chatMicActive ? 'i-solar:microphone-bold' : 'i-solar:microphone-3-bold-duotone'" class="h-4 w-4" />
      </button>
      <BasicTextarea
        v-model="messageInput"
        :placeholder="t('chat.input.placeholder')"
        :submit-on-enter="submitOnEnter"
        rows="1"
        border="solid 2 neutral-200/60 dark:neutral-700/60"
        text="neutral-500 hover:neutral-600 dark:neutral-100 dark:hover:neutral-200 placeholder:neutral-400 placeholder:hover:neutral-500 placeholder:dark:neutral-300 placeholder:dark:hover:neutral-400"
        bg="neutral-100/80 dark:neutral-950/80"
        max-h="[10lh]" min-h="[calc(1lh+4px+4px)]"
        w-full resize-none overflow-y-scroll rounded="[1lh]" px-4 py-0.5 outline-none backdrop-blur-md
        transition="all duration-250 ease-in-out placeholder:all placeholder:duration-250 placeholder:ease-in-out"
        :class="[themeColorsHueDynamic ? 'transition-colors-none placeholder:transition-colors-none' : '']"
        @submit="handleSend"
        @compositionstart="isComposing = true"
        @compositionend="isComposing = false"
      />
      <button
        v-if="showSendButton"
        w="[calc(1lh+4px+4px)]" h="[calc(1lh+4px+4px)]"
        aspect-square
        flex
        items-center
        self-end
        justify-center
        rounded-full
        outline-none
        backdrop-blur-md
        text="neutral-500 hover:neutral-600 dark:neutral-900 dark:hover:neutral-800"
        bg="primary-50/80 dark:neutral-100/80 hover:neutral-50"
        transition="all duration-250 ease-in-out"
        @click="handleSend"
      >
        <div class="i-solar:arrow-up-outline" />
      </button>
    </div>
    <div v-if="showChatMicError" class="pt-1 text-[11px] text-rose-500">
      {{ transcriptionError }}
    </div>
  </div>
  <div v-else flex gap-2 class="ph-no-capture lt-md:h-full">
    <button
      type="button"
      class="mb-4 flex h-9 w-9 items-center justify-center self-end rounded-full border border-primary-300/40 bg-primary-100/70 text-primary-700 shadow-sm backdrop-blur-md transition hover:bg-primary-100 disabled:cursor-not-allowed disabled:opacity-40 dark:border-primary-400/30 dark:bg-primary-500/20 dark:text-primary-100 dark:hover:bg-primary-500/30"
      :class="chatMicActive ? 'ring-2 ring-primary-300/70 dark:ring-primary-300/60' : ''"
      :title="chatMicButtonTitle"
      :disabled="!canListenToTranscription"
      @click="toggleChatMic"
    >
      <div :class="chatMicActive ? 'i-solar:microphone-bold' : 'i-solar:microphone-3-bold-duotone'" class="h-5 w-5" />
    </button>
    <div
      :class="[
        'relative',
        'w-full',
        'bg-primary-200/20 dark:bg-primary-400/20',
      ]"
    >
      <BasicTextarea
        v-model="messageInput"
        :placeholder="t('chat.input.placeholder')"
        :submit-on-enter="submitOnEnter"
        text="primary-600 dark:primary-100 placeholder:primary-500 dark:placeholder:primary-200"
        bg="transparent"
        min-h="[100px]" max-h="[300px]" w-full
        rounded-t-xl p-4 font-medium
        outline-none transition="all duration-250 ease-in-out placeholder:all placeholder:duration-250 placeholder:ease-in-out"
        @submit="handleSend"
        @compositionstart="isComposing = true"
        @compositionend="isComposing = false"
      />
    </div>
  </div>
</template>
