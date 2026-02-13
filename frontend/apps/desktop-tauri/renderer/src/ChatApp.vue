<script setup lang="ts">
import { onMounted, onUnmounted } from "vue";

import { useChatStore } from "@whalewhisper/app-core/stores/chat";
import { useSpeechOutputStore } from "@whalewhisper/app-core/stores/speech-output";
import DesktopChatOverlay from "./components/DesktopChatOverlay.vue";
import { closeChatWindow, emitDesktopActionToken } from "./services/desktop";

const fillStyle = {
  left: "0px",
  top: "0px",
  width: "100%",
  height: "100%",
};
const chatStore = useChatStore();
const speechOutput = useSpeechOutputStore();
let disposeSpecialToken: null | (() => void) = null;
let disposeSpeechOutput: null | (() => void) = null;

async function handleClose() {
  await closeChatWindow();
}

onMounted(() => {
  chatStore.connect();
  disposeSpecialToken = chatStore.onTokenSpecial(async (special) => {
    await emitDesktopActionToken(special);
  });
  disposeSpeechOutput = chatStore.onAssistantFinal(async (message) => {
    await speechOutput.speak(message.content);
  });
});

onUnmounted(() => {
  disposeSpecialToken?.();
  disposeSpeechOutput?.();
});
</script>

<template>
  <div class="relative h-full w-full" :style="{ width: '100%', height: '100%' }">
    <DesktopChatOverlay
      :visible="true"
      :position-style="fillStyle"
      @close="handleClose"
    />
  </div>
</template>
