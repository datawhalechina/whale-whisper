<script setup lang="ts">
import type {
  ChatAssistantMessage,
  ChatContentPart,
  ChatHistoryItem,
  ChatSlices,
} from "@whalewhisper/app-core/types/chat";

import { computed, onMounted, ref, watch } from "vue";
import { storeToRefs } from "pinia";

import { useI18n } from "@whalewhisper/app-core/composables/use-i18n";
import { useTheme } from "@whalewhisper/app-core/composables/use-theme";
import { useChatStore } from "@whalewhisper/app-core/stores/chat";
import { useTranscriptionStore } from "@whalewhisper/app-core/stores/transcription";

const props = defineProps<{
  visible: boolean;
  positionStyle: Record<string, string>;
}>();

const emit = defineEmits<{
  (e: "close"): void;
}>();

const chatStore = useChatStore();
const transcriptionStore = useTranscriptionStore();
const { messages, sending, streamingMessage } = storeToRefs(chatStore);
const {
  listening: transcriptionListening,
  listeningSource: transcriptionListeningSource,
  canListen: canListenToTranscription,
  error: transcriptionError,
} = storeToRefs(transcriptionStore);
const { t } = useI18n();
const { isDark } = useTheme();

const messageInput = ref("");
const isComposing = ref(false);
const historyRef = ref<HTMLDivElement | null>(null);
const isDraggingHistory = ref(false);
let dragStartY = 0;
let dragStartScrollTop = 0;

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

const streaming = computed<ChatAssistantMessage>(() => {
  return (
    streamingMessage.value ?? {
      id: "streaming",
      role: "assistant",
      content: "",
      slices: [],
      tool_results: [],
      createdAt: Date.now(),
    }
  );
});

const renderMessages = computed<ChatHistoryItem[]>(() => {
  if (!sending.value) {
    return messages.value;
  }

  const streamTs = streaming.value?.createdAt;
  if (!streamTs) {
    return messages.value;
  }

  const hasStreamAlready = messages.value.some(
    (msg) => msg?.createdAt === streamTs
  );
  if (hasStreamAlready) {
    return messages.value;
  }

  return [...messages.value, streaming.value];
});

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

function handleKeydown(event: KeyboardEvent) {
  if (event.key !== "Enter" || event.shiftKey) return;
  event.preventDefault();
  handleSend();
}

function resolveText(content?: string | ChatContentPart[]) {
  if (!content) return "";
  if (typeof content === "string") return content;
  return content.map((part) => part.text).join("");
}

function resolveSlicesText(slices: ChatSlices[]) {
  return slices
    .map((slice) => {
      if (slice.type === "text") return slice.text;
      if (slice.type === "tool-call") {
        return `[tool] ${slice.toolCall.toolName}(${slice.toolCall.args})`;
      }
      if (slice.type === "tool-call-result") {
        return `[result] ${resolveText(slice.result)}`;
      }
      return "";
    })
    .filter(Boolean)
    .join("\n");
}

function resolveMessageText(message: ChatHistoryItem) {
  if (message.role === "error") {
    return resolveText(message.content as string);
  }
  if ("slices" in message && Array.isArray(message.slices) && message.slices.length) {
    return resolveSlicesText(message.slices);
  }
  return resolveText(message.content as string | ChatContentPart[]);
}

function bubbleStyle(role: ChatHistoryItem["role"]) {
  const dark = isDark.value;
  if (role === "user") {
    return {
      backgroundColor: dark ? "rgba(24, 24, 27, 0.7)" : "rgba(244, 244, 245, 0.85)",
      color: dark ? "#f5f5f5" : "#1f2937",
    };
  }
  if (role === "error") {
    return {
      backgroundColor: dark ? "rgba(127, 29, 29, 0.6)" : "rgba(254, 226, 226, 0.85)",
      color: dark ? "#fee2e2" : "#b91c1c",
    };
  }
  return {
    backgroundColor: dark ? "rgba(30, 58, 138, 0.5)" : "rgba(239, 246, 255, 0.85)",
    color: dark ? "#dbeafe" : "#1d4ed8",
  };
}

function scrollToBottom() {
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      if (!historyRef.value) return;
      historyRef.value.scrollTop = historyRef.value.scrollHeight;
    });
  });
}

function handleHistoryPointerDown(event: PointerEvent) {
  if (event.button !== 0) return;
  const el = historyRef.value;
  if (!el) return;
  isDraggingHistory.value = true;
  dragStartY = event.clientY;
  dragStartScrollTop = el.scrollTop;
  el.setPointerCapture(event.pointerId);
}

function handleHistoryPointerMove(event: PointerEvent) {
  if (!isDraggingHistory.value) return;
  const el = historyRef.value;
  if (!el) return;
  const delta = event.clientY - dragStartY;
  el.scrollTop = dragStartScrollTop - delta;
}

function handleHistoryPointerUp(event: PointerEvent) {
  if (!isDraggingHistory.value) return;
  const el = historyRef.value;
  isDraggingHistory.value = false;
  if (el?.hasPointerCapture(event.pointerId)) {
    el.releasePointerCapture(event.pointerId);
  }
}

watch([renderMessages, () => sending.value], scrollToBottom, {
  deep: true,
  flush: "post",
});
watch(
  () => props.visible,
  (visible) => {
    if (!visible) return;
    scrollToBottom();
  },
  { flush: "post" }
);
onMounted(scrollToBottom);
</script>

<template>
  <div
    v-show="visible"
    class="pointer-events-auto absolute z-30 flex h-full flex-col gap-2"
    data-controls-hitbox
    :style="positionStyle"
  >
    <div class="flex items-center justify-between">
      <span class="text-[11px] font-semibold text-neutral-600">
        {{ t("chat.title") }}
      </span>
      <button
        type="button"
        class="rounded-full border border-white/60 bg-white/70 p-1 text-neutral-500 shadow-sm backdrop-blur-md transition hover:text-neutral-800 dark:border-neutral-700/60 dark:bg-neutral-900/70 dark:text-neutral-300 dark:hover:text-neutral-100"
        :title="t('common.close')"
        @click="emit('close')"
      >
        <div class="i-solar:close-circle-bold-duotone h-4 w-4" />
      </button>
    </div>

    <div
      ref="historyRef"
      class="chat-history-scroll flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto pr-1"
      :class="[isDraggingHistory ? 'cursor-grabbing select-none' : 'cursor-grab']"
      @pointerdown="handleHistoryPointerDown"
      @pointermove="handleHistoryPointerMove"
      @pointerup="handleHistoryPointerUp"
      @pointercancel="handleHistoryPointerUp"
    >
      <div
        v-for="(message, index) in renderMessages"
        :key="message?.createdAt ?? index"
        class="flex w-full"
        :class="message.role === 'user' ? 'justify-end' : 'justify-start'"
      >
        <div
          class="max-w-[95%] rounded-xl px-3 py-2 text-xs shadow-sm backdrop-blur-md"
          :style="bubbleStyle(message.role)"
        >
          <div class="mb-1 text-[10px] text-black/50 dark:text-white/60">
            {{
              message.role === "user"
                ? t("chat.label.user")
                : message.role === "error"
                  ? t("chat.label.system")
                  : t("chat.label.assistant")
            }}
          </div>
          <div
            v-if="resolveMessageText(message)"
            class="whitespace-pre-wrap break-words"
          >
            {{ resolveMessageText(message) }}
          </div>
          <div
            v-else-if="sending && index === renderMessages.length - 1"
            class="text-neutral-400"
          >
            ...
          </div>
        </div>
      </div>
    </div>

    <div>
      <div class="flex items-end gap-1">
        <button
          type="button"
          class="mb-0.5 flex h-8 w-8 items-center justify-center rounded-full border border-white/60 bg-white/70 text-neutral-500 shadow-sm backdrop-blur-md transition hover:text-neutral-800 disabled:cursor-not-allowed disabled:opacity-40 dark:border-neutral-700/60 dark:bg-neutral-900/70 dark:text-neutral-300 dark:hover:text-neutral-100"
          :class="chatMicActive
            ? 'border-primary-300/80 bg-primary-100/80 text-primary-600 dark:border-primary-300/70 dark:bg-primary-500/25 dark:text-primary-100'
            : ''"
          :title="chatMicButtonTitle"
          :disabled="!canListenToTranscription"
          @click="toggleChatMic"
        >
          <div :class="chatMicActive ? 'i-solar:microphone-bold' : 'i-solar:microphone-3-bold-duotone'" class="h-4 w-4" />
        </button>
        <textarea
          v-model="messageInput"
          rows="1"
          class="min-h-[34px] flex-1 resize-none rounded-xl border border-white/50 bg-white/70 px-3 py-2 text-sm text-neutral-700 shadow-sm outline-none backdrop-blur-md transition focus:border-primary-300 dark:border-neutral-700/60 dark:bg-neutral-900/70 dark:text-neutral-100 dark:focus:border-primary-400"
          :placeholder="t('chat.input.placeholder')"
          @keydown="handleKeydown"
          @compositionstart="isComposing = true"
          @compositionend="isComposing = false"
        ></textarea>
        <button
          v-if="showSendButton"
          type="button"
          class="flex h-9 w-9 items-center justify-center rounded-full bg-primary-500/80 text-white shadow-sm transition hover:bg-primary-500 dark:bg-primary-400/80 dark:hover:bg-primary-400"
          @click="handleSend"
        >
          <div class="i-solar:arrow-up-outline h-4 w-4" />
        </button>
      </div>
      <div v-if="showChatMicError" class="pt-1 text-[11px] text-rose-500">
        {{ transcriptionError }}
      </div>
    </div>
  </div>
</template>

<style scoped>
.chat-history-scroll {
  scrollbar-width: none;
  -ms-overflow-style: none;
}

.chat-history-scroll::-webkit-scrollbar {
  width: 0;
  height: 0;
}
</style>
