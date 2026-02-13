<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import SelectMenu from "./ui/SelectMenu.vue";

type SelectOption = {
  id: string;
  label: string;
  description?: string;
};

type HearingState = {
  enabled?: boolean;
  selectedDeviceId?: string;
  audioInputs?: Array<{ deviceId: string; label: string }>;
  volumeLevel?: number;
  speechThreshold?: number;
  isSpeaking?: boolean;
  speechDetected?: boolean;
  permission?: string;
  error?: string | null;
  refreshDevices?: () => void | Promise<void>;
};

type TranscriptionState = {
  enabled?: boolean;
  autoSend?: boolean;
  language?: string;
  vadMinSpeechMs?: number;
  vadSilenceMs?: number;
  listening?: boolean;
  canListen?: boolean;
  supported?: boolean;
  interimText?: string;
  lastTranscript?: string;
  error?: string | null;
  startListening?: () => void;
  stopListening?: () => void;
};

type SpeechOutputState = {
  enabled?: boolean;
  rate?: number;
  pitch?: number;
  volume?: number;
  streaming?: boolean;
  supported?: boolean;
  lastError?: string | null;
  speak?: (text: string) => void | Promise<void>;
  stop?: () => void;
};

const props = defineProps<{
  locale?: string;
  hearing?: HearingState;
  transcription?: TranscriptionState;
  speechOutput?: SpeechOutputState;
  t?: (key: string) => string;
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
  "audio.input.title": "Audio Input",
  "audio.microphone.title": "Microphone",
  "audio.microphone.desc": "Enable audio input and monitor volume levels.",
  "audio.microphone.permissionDenied": "Microphone permission is denied. Please allow access.",
  "audio.input.device": "Input Device",
  "audio.input.placeholder": "Select microphone",
  "audio.vad.label": "VAD Threshold",
  "audio.vad.detected": "Speech detected:",
  "audio.stt.title": "Speech-to-Text",
  "audio.stt.desc": "Use browser speech recognition.",
  "audio.stt.start": "Start Listening",
  "audio.stt.stop": "Stop Listening",
  "audio.stt.language": "Language",
  "audio.stt.vad.minSpeech": "Min speech (ms)",
  "audio.stt.vad.silence": "Silence timeout (ms)",
  "audio.stt.autosend": "Auto send to chat",
  "audio.stt.listening": "Listening:",
  "audio.stt.last": "Last:",
  "audio.output.title": "Speech Output",
  "audio.tts.title": "Text-to-Speech",
  "audio.tts.desc": "Speak assistant replies.",
  "audio.tts.voice": "Voice",
  "audio.tts.placeholder": "Select voice",
  "audio.tts.unsupported": "Speech synthesis not supported.",
  "audio.tts.rate": "Rate",
  "audio.tts.pitch": "Pitch",
  "audio.tts.volume": "Volume",
  "audio.tts.streaming": "Low latency",
  "audio.tts.streaming.desc": "Split long text into chunks for faster playback.",
  "audio.tts.testText": "Test text",
  "audio.tts.test.placeholder": "Type something to test",
  "audio.tts.test.play": "Play",
  "audio.tts.test.stop": "Stop",
  "audio.device.unknown": "Unknown Device",
  "audio.device.default": "Default",
  "common.enabled": "Enabled",
  "common.disabled": "Disabled",
  "common.yes": "Yes",
  "common.no": "No",
};

const fallbackZh = {
  "audio.input.title": "音频输入",
  "audio.microphone.title": "麦克风",
  "audio.microphone.desc": "启用音频输入并监测音量。",
  "audio.microphone.permissionDenied": "麦克风权限被拒绝，请允许访问。",
  "audio.input.device": "输入设备",
  "audio.input.placeholder": "选择麦克风",
  "audio.vad.label": "VAD 阈值",
  "audio.vad.detected": "检测到语音：",
  "audio.stt.title": "语音转文字",
  "audio.stt.desc": "使用浏览器语音识别。",
  "audio.stt.start": "开始监听",
  "audio.stt.stop": "停止监听",
  "audio.stt.language": "语言",
  "audio.stt.vad.minSpeech": "最短语音（ms）",
  "audio.stt.vad.silence": "静音分段（ms）",
  "audio.stt.autosend": "自动发送到聊天",
  "audio.stt.listening": "正在听写：",
  "audio.stt.last": "上次结果：",
  "audio.output.title": "语音输出",
  "audio.tts.title": "文字转语音",
  "audio.tts.desc": "朗读助手回复。",
  "audio.tts.voice": "音色",
  "audio.tts.placeholder": "选择音色",
  "audio.tts.unsupported": "当前浏览器不支持语音合成。",
  "audio.tts.rate": "语速",
  "audio.tts.pitch": "音调",
  "audio.tts.volume": "音量",
  "audio.tts.streaming": "低延迟",
  "audio.tts.streaming.desc": "将长文本分段生成，提升播放速度。",
  "audio.tts.testText": "测试文本",
  "audio.tts.test.placeholder": "输入要测试的文本",
  "audio.tts.test.play": "播放",
  "audio.tts.test.stop": "停止",
  "audio.device.unknown": "未知设备",
  "audio.device.default": "默认",
  "common.enabled": "启用",
  "common.disabled": "禁用",
  "common.yes": "是",
  "common.no": "否",
};

const fallbackText = computed(() => (isZh.value ? fallbackZh : fallbackEn));
const t = (key: string) => {
  if (props.t) {
    const resolved = props.t(key);
    if (resolved && resolved !== key) return resolved;
  }
  return fallbackText.value[key as keyof typeof fallbackEn] ?? key;
};

const micEnabled = computed({
  get: () => !!props.hearing?.enabled,
  set: (value: boolean) => {
    if (!props.hearing) return;
    props.hearing.enabled = value;
  },
});
const selectedDeviceId = computed({
  get: () => props.hearing?.selectedDeviceId ?? "",
  set: (value: string) => {
    if (!props.hearing) return;
    props.hearing.selectedDeviceId = value;
  },
});
const speechThreshold = computed({
  get: () => props.hearing?.speechThreshold ?? 30,
  set: (value: number) => {
    if (!props.hearing) return;
    props.hearing.speechThreshold = value;
  },
});

const sttEnabled = computed({
  get: () => !!props.transcription?.enabled,
  set: (value: boolean) => {
    if (!props.transcription) return;
    props.transcription.enabled = value;
  },
});
const autoSend = computed({
  get: () => !!props.transcription?.autoSend,
  set: (value: boolean) => {
    if (!props.transcription) return;
    props.transcription.autoSend = value;
  },
});
const language = computed({
  get: () => props.transcription?.language ?? "en-US",
  set: (value: string) => {
    if (!props.transcription) return;
    props.transcription.language = value;
  },
});
const vadMinSpeechMs = computed({
  get: () => props.transcription?.vadMinSpeechMs ?? 300,
  set: (value: number) => {
    if (!props.transcription) return;
    props.transcription.vadMinSpeechMs = value;
  },
});
const vadSilenceMs = computed({
  get: () => props.transcription?.vadSilenceMs ?? 700,
  set: (value: number) => {
    if (!props.transcription) return;
    props.transcription.vadSilenceMs = value;
  },
});

const ttsEnabled = computed({
  get: () => !!props.speechOutput?.enabled,
  set: (value: boolean) => {
    if (!props.speechOutput) return;
    props.speechOutput.enabled = value;
  },
});
const rate = computed({
  get: () => props.speechOutput?.rate ?? 1,
  set: (value: number) => {
    if (!props.speechOutput) return;
    props.speechOutput.rate = value;
  },
});
const pitch = computed({
  get: () => props.speechOutput?.pitch ?? 1,
  set: (value: number) => {
    if (!props.speechOutput) return;
    props.speechOutput.pitch = value;
  },
});
const volume = computed({
  get: () => props.speechOutput?.volume ?? 1,
  set: (value: number) => {
    if (!props.speechOutput) return;
    props.speechOutput.volume = value;
  },
});
const streaming = computed({
  get: () => !!props.speechOutput?.streaming,
  set: (value: boolean) => {
    if (!props.speechOutput) return;
    props.speechOutput.streaming = value;
  },
});

const deviceOptions = computed<SelectOption[]>(() => {
  const inputs = props.hearing?.audioInputs ?? [];
  const sorted = [...inputs].sort((a, b) => {
    if (a.deviceId === "default") return -1;
    if (b.deviceId === "default") return 1;
    return 0;
  });
  return sorted.map((device) => ({
    id: device.deviceId,
    label: formatDeviceLabel(device),
  }));
});

const testText = ref("");
const defaultTestText = computed(() =>
  isZh.value ? "你好，这是一段语音测试。" : "Hello! This is a voice test."
);

function playTest() {
  if (!props.speechOutput?.speak) return;
  if (!ttsEnabled.value) {
    ttsEnabled.value = true;
  }
  const text = testText.value.trim();
  if (!text) return;
  void props.speechOutput.speak(text);
}

function stopTest() {
  props.speechOutput?.stop?.();
}

function normalizeDeviceLabel(label: string) {
  if (!label) return "";
  const cleaned = label
    .replace(/\s*\([0-9a-f]{4}:[0-9a-f]{4}\)\s*/gi, " ")
    .replace(/^(default|system default|默认)\s*-\s*/i, "")
    .replace(/\s+/g, " ")
    .trim();
  return cleaned;
}

function formatDeviceLabel(device: { deviceId: string; label?: string }) {
  const cleaned = normalizeDeviceLabel(device.label || "");
  if (device.deviceId === "default") {
    if (cleaned) {
      return `${t("audio.device.default")} - ${cleaned}`;
    }
    return t("audio.device.default");
  }
  return cleaned || t("audio.device.unknown");
}

function toggleListening() {
  if (!props.transcription) return;
  if (props.transcription.listening) {
    props.transcription.stopListening?.();
  } else {
    props.transcription.startListening?.();
  }
}

onMounted(() => {
  void props.hearing?.refreshDevices?.();
  if (!testText.value) {
    testText.value = defaultTestText.value;
  }
});
</script>

<template>
  <div class="grid gap-4">
    <div class="rounded-2xl border border-neutral-200/70 bg-white/70 p-4 shadow-sm dark:border-neutral-800/70 dark:bg-neutral-950/60">
      <div class="mb-3 text-sm font-semibold text-neutral-800 dark:text-neutral-100">
        {{ t("audio.input.title") }}
      </div>
      <div class="flex flex-wrap items-center gap-4">
        <div class="relative h-24 w-24">
          <div
            class="absolute left-1/2 top-1/2 h-16 w-16 rounded-full transition-all duration-150 -translate-x-1/2 -translate-y-1/2"
            :class="micEnabled ? 'bg-primary-500/20' : 'bg-neutral-300/20 dark:bg-neutral-700/30'"
            :style="{ transform: `translate(-50%, -50%) scale(${1 + ((props.hearing?.volumeLevel ?? 0) / 100) * 0.35})` }"
          />
          <div
            class="absolute left-1/2 top-1/2 h-20 w-20 rounded-full transition-all duration-200 -translate-x-1/2 -translate-y-1/2"
            :class="micEnabled ? 'bg-primary-500/10' : 'bg-neutral-300/10 dark:bg-neutral-700/20'"
            :style="{ transform: `translate(-50%, -50%) scale(${1.2 + ((props.hearing?.volumeLevel ?? 0) / 100) * 0.5})` }"
          />
          <button
            type="button"
            class="absolute left-1/2 top-1/2 grid h-14 w-14 place-items-center rounded-full shadow-md transition-all duration-200 -translate-x-1/2 -translate-y-1/2"
            :class="micEnabled
              ? 'bg-primary-500 text-white hover:bg-primary-600 active:scale-95'
              : 'bg-neutral-200 text-neutral-600 hover:bg-neutral-300 active:scale-95 dark:bg-neutral-700 dark:text-neutral-200'"
            @click="micEnabled = !micEnabled"
          >
            <div :class="micEnabled ? 'i-solar:microphone-bold' : 'i-solar:microphone-3-bold-duotone'" class="h-6 w-6" />
          </button>
        </div>

        <div class="flex-1 space-y-2">
          <div class="text-sm font-medium text-neutral-800 dark:text-neutral-100">
            {{ t("audio.microphone.title") }}
          </div>
          <div class="text-xs text-neutral-500 dark:text-neutral-400">
            {{ t("audio.microphone.desc") }}
          </div>
          <div v-if="props.hearing?.permission === 'denied'" class="text-xs text-rose-500">
            {{ t("audio.microphone.permissionDenied") }}
          </div>
          <div v-if="props.hearing?.error" class="text-xs text-rose-500">
            {{ props.hearing.error }}
          </div>
        </div>
      </div>

      <div class="mt-4 grid gap-2">
        <label class="text-xs text-neutral-500 dark:text-neutral-400">
          {{ t("audio.input.device") }}
        </label>
        <SelectMenu
          v-model="selectedDeviceId"
          :options="deviceOptions"
          :placeholder="t('audio.input.placeholder')"
        />
      </div>
      <div class="mt-4 grid gap-2">
        <label class="flex flex-col gap-1 text-xs text-neutral-500 dark:text-neutral-400">
          {{ t("audio.vad.label") }}
          <input
            v-model.number="speechThreshold"
            type="range"
            min="5"
            max="90"
            step="1"
            class="w-full accent-primary-500"
          />
        </label>
        <div class="text-xs text-neutral-500 dark:text-neutral-400">
          {{ t("audio.vad.detected") }}
          <span
            :class="(props.hearing?.speechDetected ?? props.hearing?.isSpeaking) ? 'text-emerald-500' : 'text-neutral-400'"
          >
            {{ (props.hearing?.speechDetected ?? props.hearing?.isSpeaking) ? t("common.yes") : t("common.no") }}
          </span>
        </div>
      </div>

      <div class="mt-4 grid gap-2">
        <div class="flex items-center justify-between rounded-xl border border-neutral-200/70 bg-white/60 px-3 py-2 dark:border-neutral-800/70 dark:bg-neutral-900/60">
          <div>
            <div class="text-sm font-medium text-neutral-800 dark:text-neutral-100">
              {{ t("audio.stt.title") }}
            </div>
            <div class="text-xs text-neutral-500 dark:text-neutral-400">
              {{ t("audio.stt.desc") }}
            </div>
          </div>
          <button
            type="button"
            class="rounded-lg border border-neutral-200 bg-white/80 px-3 py-1 text-xs text-neutral-600 transition hover:text-neutral-900 dark:border-neutral-700 dark:bg-neutral-800/80 dark:text-neutral-300"
            @click="sttEnabled = !sttEnabled"
          >
            {{ sttEnabled ? t("common.disabled") : t("common.enabled") }}
          </button>
        </div>
        <div class="flex flex-wrap items-center gap-2">
          <button
            type="button"
            class="rounded-lg border border-neutral-200 bg-white/80 px-3 py-1 text-xs text-neutral-600 transition hover:text-neutral-900 disabled:opacity-60 dark:border-neutral-700 dark:bg-neutral-800/80 dark:text-neutral-300"
            :disabled="!props.transcription?.canListen"
            @click="toggleListening"
          >
            {{ props.transcription?.listening ? t("audio.stt.stop") : t("audio.stt.start") }}
          </button>
          <label class="text-xs text-neutral-500 dark:text-neutral-400">
            {{ t("audio.stt.language") }}
          </label>
          <input
            v-model="language"
            type="text"
            placeholder="en-US"
            class="w-28 rounded-lg border border-neutral-200 bg-white/80 px-2 py-1 text-xs text-neutral-700 shadow-sm outline-none transition focus:border-primary-400 dark:border-neutral-800 dark:bg-neutral-900/70 dark:text-neutral-200"
          />
          <label class="ml-2 flex items-center gap-2 text-xs text-neutral-500 dark:text-neutral-400">
            {{ t("audio.stt.vad.minSpeech") }}
            <input
              v-model.number="vadMinSpeechMs"
              type="number"
              min="100"
              max="3000"
              step="50"
              class="w-20 rounded-lg border border-neutral-200 bg-white/80 px-2 py-1 text-xs text-neutral-700 shadow-sm outline-none transition focus:border-primary-400 dark:border-neutral-800 dark:bg-neutral-900/70 dark:text-neutral-200"
            />
          </label>
          <label class="ml-2 flex items-center gap-2 text-xs text-neutral-500 dark:text-neutral-400">
            {{ t("audio.stt.vad.silence") }}
            <input
              v-model.number="vadSilenceMs"
              type="number"
              min="200"
              max="5000"
              step="50"
              class="w-20 rounded-lg border border-neutral-200 bg-white/80 px-2 py-1 text-xs text-neutral-700 shadow-sm outline-none transition focus:border-primary-400 dark:border-neutral-800 dark:bg-neutral-900/70 dark:text-neutral-200"
            />
          </label>
          <label class="ml-2 flex items-center gap-2 text-xs text-neutral-500 dark:text-neutral-400">
            <input v-model="autoSend" type="checkbox" class="accent-primary-500" />
            {{ t("audio.stt.autosend") }}
          </label>
        </div>
        <div v-if="props.transcription?.error" class="text-xs text-rose-500">
          {{ props.transcription.error }}
        </div>
        <div v-if="props.transcription?.interimText" class="text-xs text-neutral-500 dark:text-neutral-400">
          {{ t("audio.stt.listening") }} {{ props.transcription.interimText }}
        </div>
        <div v-else-if="props.transcription?.lastTranscript" class="text-xs text-neutral-500 dark:text-neutral-400">
          {{ t("audio.stt.last") }} {{ props.transcription.lastTranscript }}
        </div>
      </div>
    </div>

    <div class="rounded-2xl border border-neutral-200/70 bg-white/70 p-4 shadow-sm dark:border-neutral-800/70 dark:bg-neutral-950/60">
      <div class="mb-3 text-sm font-semibold text-neutral-800 dark:text-neutral-100">
        {{ t("audio.output.title") }}
      </div>
      <div class="flex items-center justify-between gap-3 rounded-xl border border-neutral-200/70 bg-white/60 px-3 py-2 dark:border-neutral-800/70 dark:bg-neutral-900/60">
        <div>
          <div class="text-sm font-medium text-neutral-800 dark:text-neutral-100">
            {{ t("audio.tts.title") }}
          </div>
          <div class="text-xs text-neutral-500 dark:text-neutral-400">
            {{ t("audio.tts.desc") }}
          </div>
        </div>
        <button
          type="button"
          class="rounded-lg border border-neutral-200 bg-white/80 px-3 py-1 text-xs text-neutral-600 transition hover:text-neutral-900 dark:border-neutral-700 dark:bg-neutral-800/80 dark:text-neutral-300"
          @click="ttsEnabled = !ttsEnabled"
        >
          {{ ttsEnabled ? t("common.disabled") : t("common.enabled") }}
        </button>
      </div>
      <div class="mt-3 grid gap-2">
        <div v-if="props.speechOutput?.supported === false" class="text-xs text-rose-500">
          {{ t("audio.tts.unsupported") }}
        </div>
        <div v-else-if="props.speechOutput?.lastError" class="text-xs text-rose-500">
          {{ props.speechOutput.lastError }}
        </div>
      </div>
      <div class="mt-3 grid gap-3">
        <label class="flex flex-col gap-1 text-xs text-neutral-500 dark:text-neutral-400">
          {{ t("audio.tts.rate") }}
          <input v-model.number="rate" type="range" min="0.5" max="2" step="0.1" class="w-full accent-primary-500" />
        </label>
        <label class="flex flex-col gap-1 text-xs text-neutral-500 dark:text-neutral-400">
          {{ t("audio.tts.pitch") }}
          <input v-model.number="pitch" type="range" min="0" max="2" step="0.1" class="w-full accent-primary-500" />
        </label>
        <label class="flex flex-col gap-1 text-xs text-neutral-500 dark:text-neutral-400">
          {{ t("audio.tts.volume") }}
          <input v-model.number="volume" type="range" min="0" max="1" step="0.05" class="w-full accent-primary-500" />
        </label>
      </div>
      <div class="mt-3 flex items-center justify-between rounded-xl border border-neutral-200/70 bg-white/60 px-3 py-2 dark:border-neutral-800/70 dark:bg-neutral-900/60">
        <div>
          <div class="text-sm font-medium text-neutral-800 dark:text-neutral-100">
            {{ t("audio.tts.streaming") }}
          </div>
          <div class="text-xs text-neutral-500 dark:text-neutral-400">
            {{ t("audio.tts.streaming.desc") }}
          </div>
        </div>
        <input v-model="streaming" type="checkbox" class="accent-primary-500" />
      </div>
      <div class="mt-4 grid gap-2">
        <label class="text-xs text-neutral-500 dark:text-neutral-400">
          {{ t("audio.tts.testText") }}
        </label>
        <input
          v-model="testText"
          type="text"
          :placeholder="t('audio.tts.test.placeholder')"
          class="w-full rounded-lg border border-neutral-200 bg-white/80 px-3 py-2 text-sm text-neutral-700 shadow-sm outline-none transition focus:border-primary-400 dark:border-neutral-800 dark:bg-neutral-900/70 dark:text-neutral-200"
        />
        <div class="flex items-center gap-2">
          <button
            type="button"
            class="rounded-lg border border-neutral-200 bg-white/80 px-3 py-1 text-xs text-neutral-600 transition hover:text-neutral-900 disabled:opacity-60 dark:border-neutral-700 dark:bg-neutral-800/80 dark:text-neutral-300"
            :disabled="!props.speechOutput?.supported"
            @click="playTest"
          >
            {{ t("audio.tts.test.play") }}
          </button>
          <button
            type="button"
            class="rounded-lg border border-neutral-200 bg-white/80 px-3 py-1 text-xs text-neutral-600 transition hover:text-neutral-900 disabled:opacity-60 dark:border-neutral-700 dark:bg-neutral-800/80 dark:text-neutral-300"
            :disabled="!props.speechOutput?.supported"
            @click="stopTest"
          >
            {{ t("audio.tts.test.stop") }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
