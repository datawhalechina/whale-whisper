import { useLocalStorage } from "@vueuse/core";
import { defineStore, storeToRefs } from "pinia";
import { computed, onScopeDispose, ref, watch } from "vue";

import {
  requestTtsDirect,
  supportsDirectTts,
} from "../services/audio";
import { toSpeakableTtsChunks } from "../utils/tts-chunker";
import { TtsStreamSegmenter } from "../utils/tts-stream-segmenter";
import { runTtsChunkQueue, TtsChunkQueueError } from "../utils/tts-streaming-runner";
import { useProvidersStore } from "./providers";
import { useSettingsStore } from "./settings";

type VoiceOption = {
  voiceURI: string;
  name: string;
  lang?: string;
};

export const useSpeechOutputStore = defineStore("speech-output", () => {
  const enabled = useLocalStorage("whalewhisper/audio/tts/enabled", false);
  const rate = useLocalStorage("whalewhisper/audio/tts/rate", 1);
  const pitch = useLocalStorage("whalewhisper/audio/tts/pitch", 1);
  const volume = useLocalStorage("whalewhisper/audio/tts/volume", 1);
  const streaming = useLocalStorage("whalewhisper/audio/tts/streaming", true);

  const providersStore = useProvidersStore();
  const settingsStore = useSettingsStore();
  const { speechProviderId } = storeToRefs(settingsStore);
  const localVoices = ref<SpeechSynthesisVoice[]>([]);
  const useBrowserTts = computed(
    () => speechProviderId.value === "browser-local-audio-speech"
  );
  const supported = computed(() => {
    if (typeof window === "undefined") return false;
    if (useBrowserTts.value) {
      return "speechSynthesis" in window;
    }
    return true;
  });
  const providerMetadata = computed(() =>
    providersStore.getProviderMetadata(speechProviderId.value)
  );
  const providerConfig = computed(() =>
    providersStore.getProviderConfig(speechProviderId.value)
  );
  const remoteVoices = computed<VoiceOption[]>(() => {
    const options = providersStore.getProviderVoices(speechProviderId.value);
    return options.map((option) => ({
      voiceURI: option.id,
      name: option.label,
      lang: option.description,
    }));
  });
  const voices = computed<VoiceOption[]>(() => {
    if (useBrowserTts.value) {
      return localVoices.value.map((voice) => ({
        voiceURI: voice.voiceURI,
        name: voice.name,
        lang: voice.lang,
      }));
    }
    return remoteVoices.value;
  });
  const resolvedVoiceId = computed(() => providerConfig.value?.voice || "");
  const audioElement = ref<HTMLAudioElement | null>(null);
  const lastError = ref<string | null>(null);
  let remoteController: AbortController | null = null;
  let streamController: AbortController | null = null;
  let requestQueueTail: Promise<void> = Promise.resolve();
  let activeObjectUrl: string | null = null;
  let audioContext: AudioContext | null = null;
  let gainNode: GainNode | null = null;
  let activeSources: AudioBufferSourceNode[] = [];
  let scheduledTime = 0;
  const assistantStreamSegmenter = new TtsStreamSegmenter();
  const incrementalStreamingEnabled = computed(
    () => streaming.value && !useBrowserTts.value
  );
  let assistantStreamActive = false;
  let assistantStreamTaskTail: Promise<void> = Promise.resolve();
  let assistantStreamPlaybackTail: Promise<void> = Promise.resolve();
  let assistantStreamStartedChunks = 0;
  let assistantStreamQueueVersion = 0;
  let assistantStreamChunks: string[] = [];
  let assistantStreamFailedChunkIndex: number | null = null;

  function resolveTtsEngineId() {
    const metadataEngineId = providerMetadata.value?.engineId;
    if (typeof metadataEngineId === "string" && metadataEngineId.trim()) {
      return metadataEngineId.trim();
    }
    if (speechProviderId.value === "volcengine-speech" || speechProviderId.value === "volcengine") {
      return "volcengine-speech";
    }
    if (
      speechProviderId.value === "alibaba-cloud-model-studio-speech" ||
      speechProviderId.value === "alibaba-cloud-model-studio"
    ) {
      return "alibaba-cloud-model-studio-speech";
    }
    return "";
  }

  async function requestTtsDirectSerial(params: Parameters<typeof requestTtsDirect>[0]) {
    const previous = requestQueueTail;
    let release: (() => void) | null = null;
    requestQueueTail = new Promise<void>((resolve) => {
      release = resolve;
    });

    await previous;
    try {
      if (params.signal?.aborted) {
        throw new DOMException("Aborted", "AbortError");
      }
      return await requestTtsDirect(params);
    } finally {
      release?.();
    }
  }

  function isRetriableTtsError(error: unknown) {
    if (error instanceof DOMException && error.name === "AbortError") {
      return false;
    }
    if (!(error instanceof Error)) {
      return false;
    }
    const status = Number((error as Error & { status?: number }).status);
    if (status === 502 || status === 503 || status === 504 || status === 429) {
      return true;
    }
    const message = error.message.toLowerCase();
    return (
      message.includes("bad gateway") ||
      message.includes("gateway timeout") ||
      message.includes("failed to fetch") ||
      message.includes("networkerror") ||
      message.includes("502")
    );
  }

  async function sleep(ms: number, signal?: AbortSignal) {
    if (!ms) return;
    await new Promise<void>((resolve, reject) => {
      const timer = setTimeout(() => {
        cleanup();
        resolve();
      }, ms);
      const onAbort = () => {
        cleanup();
        reject(new DOMException("Aborted", "AbortError"));
      };
      const cleanup = () => {
        clearTimeout(timer);
        signal?.removeEventListener("abort", onAbort);
      };
      if (signal?.aborted) {
        onAbort();
        return;
      }
      signal?.addEventListener("abort", onAbort, { once: true });
    });
  }

  async function requestTtsDirectWithRetry(
    params: Parameters<typeof requestTtsDirect>[0],
    options?: { maxAttempts?: number }
  ) {
    const maxAttempts = Math.max(1, options?.maxAttempts ?? 1);
    for (let attempt = 1; attempt <= maxAttempts; attempt++) {
      try {
        return await requestTtsDirectSerial(params);
      } catch (error) {
        const shouldRetry = attempt < maxAttempts && isRetriableTtsError(error);
        if (!shouldRetry) {
          throw error;
        }
        await sleep(180 * attempt, params.signal);
      }
    }
    throw new Error("Direct TTS request failed.");
  }

  async function requestRemoteTtsBlob(
    text: string,
    signal: AbortSignal,
    options?: { maxAttempts?: number }
  ) {
    const engineId = resolveTtsEngineId();
    const config = buildRemoteConfig();

    if (!supportsDirectTts(engineId)) {
      throw new Error(`Direct TTS is not supported for provider: ${speechProviderId.value}`);
    }

    return await requestTtsDirectWithRetry(
      {
        engineId,
        text,
        config,
        signal,
      },
      options
    );
  }

  function refreshVoices() {
    if (!supported.value) return;
    if (useBrowserTts.value) {
      localVoices.value = window.speechSynthesis.getVoices();
    } else {
      void providersStore.refreshProvider(speechProviderId.value);
    }
  }

  function getSelectedVoice() {
    if (!resolvedVoiceId.value) return undefined;
    return localVoices.value.find((voice) => voice.voiceURI === resolvedVoiceId.value);
  }

  function stopRemotePlayback(options?: { invalidateQueue?: boolean }) {
    if (remoteController) {
      remoteController.abort();
      remoteController = null;
    }
    stopStreamingPlayback();
    resetAssistantStreamState({ invalidateQueue: options?.invalidateQueue ?? true });
    if (audioElement.value) {
      audioElement.value.pause();
      audioElement.value.src = "";
    }
    if (activeObjectUrl) {
      URL.revokeObjectURL(activeObjectUrl);
      activeObjectUrl = null;
    }
  }

  function ensureAudioElement() {
    if (!audioElement.value && typeof Audio !== "undefined") {
      audioElement.value = new Audio();
    }
    return audioElement.value;
  }

  function clampVolume(value: number) {
    return Math.min(Math.max(value, 0), 1);
  }

  function scheduleDecodedBuffer(ctx: AudioContext, buffer: AudioBuffer) {
    const startAt = Math.max(ctx.currentTime, scheduledTime);
    const source = ctx.createBufferSource();
    source.buffer = buffer;
    if (gainNode) {
      source.connect(gainNode);
    } else {
      source.connect(ctx.destination);
    }
    source.start(startAt);
    scheduledTime = startAt + buffer.duration;
    activeSources.push(source);
    source.onended = () => {
      activeSources = activeSources.filter((item) => item !== source);
    };
  }

  function ensureAudioContext() {
    if (typeof window === "undefined") return null;
    if (!audioContext) {
      const AudioContextCtor =
        window.AudioContext || (window as typeof window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
      if (!AudioContextCtor) return null;
      audioContext = new AudioContextCtor();
      gainNode = audioContext.createGain();
      gainNode.connect(audioContext.destination);
    }
    return audioContext;
  }

  function stopStreamingPlayback() {
    if (streamController) {
      streamController.abort();
      streamController = null;
    }
    if (activeSources.length > 0) {
      activeSources.forEach((source) => {
        try {
          source.stop();
        } catch {
          // Ignore errors when stopping already-finished sources.
        }
      });
      activeSources = [];
    }
    scheduledTime = 0;
  }

  function resetAssistantStreamState(options?: { invalidateQueue?: boolean }) {
    assistantStreamActive = false;
    assistantStreamPlaybackTail = Promise.resolve();
    assistantStreamStartedChunks = 0;
    assistantStreamChunks = [];
    assistantStreamFailedChunkIndex = null;
    assistantStreamSegmenter.reset();
    if (options?.invalidateQueue) {
      assistantStreamQueueVersion += 1;
      assistantStreamTaskTail = Promise.resolve();
    }
  }

  function queueAssistantStreamTask(task: () => Promise<void>) {
    const version = assistantStreamQueueVersion;
    const runIfCurrent = async () => {
      if (version !== assistantStreamQueueVersion) return;
      await task();
    };
    assistantStreamTaskTail = assistantStreamTaskTail.then(runIfCurrent, runIfCurrent);
    return assistantStreamTaskTail;
  }

  async function ensureAssistantStreamStarted() {
    if (!incrementalStreamingEnabled.value) return false;
    if (!supported.value || !enabled.value) return false;
    if (assistantStreamActive && streamController && !streamController.signal.aborted) {
      return true;
    }

    const ctx = ensureAudioContext();
    if (!ctx) return false;

    if (ctx.state === "suspended") {
      await ctx.resume();
    }
    if (gainNode) {
      gainNode.gain.value = clampVolume(volume.value);
    }

    stopRemotePlayback({ invalidateQueue: false });
    assistantStreamSegmenter.reset();
    assistantStreamPlaybackTail = Promise.resolve();
    assistantStreamStartedChunks = 0;
    assistantStreamChunks = [];
    assistantStreamFailedChunkIndex = null;
    streamController = new AbortController();
    scheduledTime = ctx.currentTime;
    assistantStreamActive = true;
    return true;
  }

  function scheduleAssistantChunkPlayback(chunk: string, chunkIndex: number) {
    assistantStreamPlaybackTail = assistantStreamPlaybackTail
      .catch(() => undefined)
      .then(async () => {
        if (!assistantStreamActive || !streamController) return;
        if (
          assistantStreamFailedChunkIndex !== null &&
          chunkIndex > assistantStreamFailedChunkIndex
        ) {
          return;
        }
        const ctx = ensureAudioContext();
        if (!ctx || streamController.signal.aborted) return;

          const buffer = await fetchTtsBuffer(chunk, streamController, ctx, {
            maxAttempts: 1,
          });
        if (!buffer || streamController.signal.aborted) return;
        scheduleDecodedBuffer(ctx, buffer);
        assistantStreamStartedChunks += 1;
      })
      .catch((error) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        if (
          assistantStreamFailedChunkIndex === null ||
          chunkIndex < assistantStreamFailedChunkIndex
        ) {
          assistantStreamFailedChunkIndex = chunkIndex;
        }
        console.warn("[TTS] stream chunk failed, defer to merged fallback:", {
          index: chunkIndex,
          chunk,
          error: error instanceof Error ? error.message : String(error),
        });
      });
  }

  function flushAssistantSegmenter(finalize: boolean) {
    const chunks = assistantStreamSegmenter.drain(finalize);
    if (chunks.length === 0) return;
    const baseIndex = assistantStreamChunks.length;
    chunks.forEach((chunk, offset) => {
      const chunkIndex = baseIndex + offset;
      assistantStreamChunks.push(chunk);
      scheduleAssistantChunkPlayback(chunk, chunkIndex);
    });
  }

  function pushAssistantLiteral(literal: string) {
    if (!literal) return;
    if (!incrementalStreamingEnabled.value) return;
    if (!supported.value || !enabled.value) return;
    void queueAssistantStreamTask(async () => {
      const started = await ensureAssistantStreamStarted();
      if (!started) return;
      assistantStreamSegmenter.appendLiteral(literal);
      flushAssistantSegmenter(false);
    });
  }

  function pushAssistantSpecial(_special: string) {
    if (!incrementalStreamingEnabled.value) return;
    if (!supported.value || !enabled.value) return;
    void queueAssistantStreamTask(async () => {
      const started = await ensureAssistantStreamStarted();
      if (!started) return;
      assistantStreamSegmenter.appendSpecialMarker();
      flushAssistantSegmenter(false);
    });
  }

  async function endAssistantStream(finalText?: string) {
    if (!incrementalStreamingEnabled.value) {
      if (finalText?.trim()) {
        await speak(finalText);
      }
      return;
    }

    await queueAssistantStreamTask(async () => {
      if (!assistantStreamActive) {
        if (finalText?.trim()) {
          await speak(finalText);
        }
        return;
      }
      assistantStreamSegmenter.appendFlushMarker();
      flushAssistantSegmenter(true);
      try {
        await assistantStreamPlaybackTail;
        if (
          assistantStreamFailedChunkIndex !== null &&
          streamController &&
          !streamController.signal.aborted
        ) {
          const ctx = ensureAudioContext();
          const remainingText = assistantStreamChunks
            .slice(assistantStreamFailedChunkIndex)
            .join("");
          if (ctx && remainingText.trim()) {
            console.warn("[TTS] stream fallback to merged remainder:", {
              failedIndex: assistantStreamFailedChunkIndex,
              remainingChunks: assistantStreamChunks.length - assistantStreamFailedChunkIndex,
            });
            const fallbackBuffer = await fetchTtsBuffer(
              remainingText,
              streamController,
              ctx,
              { maxAttempts: 1 }
            );
            if (fallbackBuffer && !streamController.signal.aborted) {
              scheduleDecodedBuffer(ctx, fallbackBuffer);
              assistantStreamStartedChunks += 1;
            }
          }
        }
      } finally {
        if (streamController && streamController.signal.aborted) {
          // Keep current abort state from explicit stop/interrupt.
        }
        assistantStreamActive = false;
        assistantStreamSegmenter.reset();
        assistantStreamPlaybackTail = Promise.resolve();
        assistantStreamStartedChunks = 0;
      }
    });
  }

  function buildRemoteConfig() {
    const config: Record<string, unknown> = {
      ...(providerConfig.value?.extra ?? {}),
    };
    const isAlibaba = speechProviderId.value === "alibaba-cloud-model-studio-speech";
    const isVolcengine = speechProviderId.value === "volcengine-speech";
    if (providerConfig.value?.apiKey) {
      config.apiKey = providerConfig.value.apiKey;
    }
    if (providerConfig.value?.baseUrl) {
      config.baseUrl = providerConfig.value.baseUrl;
      config.base_url = providerConfig.value.baseUrl;
    }
    let model = providerConfig.value?.model;
    const voice = resolvedVoiceId.value;
    if (model) {
      config.model = model;
    }
    if (voice) {
      config.voice = voice;
    }
    if (rate.value && rate.value !== 1) {
      if (isAlibaba) {
        config.rate = rate.value;
      } else {
        config.speed = rate.value;
      }
    }
    if (isAlibaba && pitch.value && pitch.value !== 1) {
      config.pitch = pitch.value;
    }
    if (isVolcengine) {
      const appId = String(providerConfig.value?.extra?.appId ?? providerConfig.value?.extra?.appid ?? "").trim();
      if (appId) {
        config.appId = appId;
      }
    }
    return config;
  }

  async function fetchTtsBuffer(
    text: string,
    controller: AbortController,
    ctx: AudioContext,
    options?: { maxAttempts?: number }
  ) {
    const blob = await requestRemoteTtsBlob(text, controller.signal, {
      maxAttempts: Math.max(1, options?.maxAttempts ?? 1),
    });
    if (controller.signal.aborted) {
      throw new DOMException("Aborted", "AbortError");
    }
    const arrayBuffer = await blob.arrayBuffer();
    if (controller.signal.aborted) {
      throw new DOMException("Aborted", "AbortError");
    }
    return await ctx.decodeAudioData(arrayBuffer.slice(0));
  }

  async function speakRemoteStreaming(text: string, ctx: AudioContext) {
    if (ctx.state === "suspended") {
      await ctx.resume();
    }
    if (gainNode) {
      gainNode.gain.value = clampVolume(volume.value);
    }

    const controller = new AbortController();
    streamController = controller;
    const chunks = toSpeakableTtsChunks(text);
    if (chunks.length === 0) return;

    scheduledTime = ctx.currentTime;

    try {
      await runTtsChunkQueue(
        chunks,
        async (chunk) => {
          if (controller.signal.aborted) return;
          const buffer = await fetchTtsBuffer(chunk, controller, ctx, {
            maxAttempts: 1,
          });
          if (!buffer || controller.signal.aborted) return;
          scheduleDecodedBuffer(ctx, buffer);
        },
        {
          stopOnError: true,
          onChunkError: (error, context) => {
            console.warn("[TTS] chunk failed:", {
              index: context.index,
              total: context.total,
              chunk: context.chunk,
              error: error instanceof Error ? error.message : String(error),
            });
          },
        }
      );
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") {
        throw error;
      }
      if (error instanceof TtsChunkQueueError) {
        const remainingChunks = chunks.slice(error.context.index);
        const remainingText = remainingChunks.join("");
        if (remainingText.trim()) {
          console.warn("[TTS] fallback to merged remainder after chunk failure:", {
            failedIndex: error.context.index,
            remainingChunks: remainingChunks.length,
          });
          const fallbackBuffer = await fetchTtsBuffer(remainingText, controller, ctx, {
            maxAttempts: 1,
          });
          if (!controller.signal.aborted && fallbackBuffer) {
            scheduleDecodedBuffer(ctx, fallbackBuffer);
            return;
          }
        }
      }
      throw error;
    } finally {
      if (streamController === controller) {
        streamController = null;
      }
    }
  }

  async function speak(text: string) {
    lastError.value = null;
    if (!supported.value) {
      lastError.value = "Audio output is not supported or API base URL is not configured.";
      return;
    }
    if (!enabled.value) {
      lastError.value = "Text-to-speech is disabled.";
      return;
    }
    if (!text.trim()) return;

    if (useBrowserTts.value) {
      const utterance = new SpeechSynthesisUtterance(text);
      const selected = getSelectedVoice();
      if (selected) {
        utterance.voice = selected;
      }
      utterance.rate = rate.value;
      utterance.pitch = pitch.value;
      utterance.volume = Math.min(Math.max(volume.value, 0), 1);
      window.speechSynthesis.speak(utterance);
      return;
    }

    stopRemotePlayback();
    if (streaming.value) {
      const ctx = ensureAudioContext();
      if (ctx) {
        try {
          await speakRemoteStreaming(text, ctx);
        } catch (error) {
          if (error instanceof DOMException && error.name === "AbortError") return;
          lastError.value = error instanceof Error ? error.message : String(error);
          console.warn(
            "TTS playback failed:",
            error instanceof Error ? error.message : error
          );
        }
        return;
      }
    }

    const element = ensureAudioElement();
    if (!element) return;

    const controller = new AbortController();
    remoteController = controller;
    try {
      const blob = await requestRemoteTtsBlob(text, controller.signal);
      if (controller.signal.aborted) return;
      const objectUrl = URL.createObjectURL(blob);
      activeObjectUrl = objectUrl;
      element.src = objectUrl;
      element.volume = clampVolume(volume.value);
      await element.play();
    } catch (error) {
      if (controller.signal.aborted) return;
      lastError.value = error instanceof Error ? error.message : String(error);
      console.warn(
        "TTS playback failed:",
        error instanceof Error ? error.message : error
      );
    } finally {
      remoteController = null;
    }
  }

  function stop() {
    if (!supported.value) return;
    if (useBrowserTts.value) {
      window.speechSynthesis.cancel();
      return;
    }
    stopRemotePlayback();
  }

  if (typeof window !== "undefined" && "speechSynthesis" in window) {
    window.speechSynthesis.onvoiceschanged = () => {
      refreshVoices();
    };
    refreshVoices();
  }

  watch(
    () => speechProviderId.value,
    () => {
      refreshVoices();
      stop();
    }
  );

  watch(
    () => volume.value,
    (next) => {
      if (audioElement.value) {
        audioElement.value.volume = clampVolume(next);
      }
      if (gainNode) {
        gainNode.gain.value = clampVolume(next);
      }
    }
  );

  onScopeDispose(() => {
    stop();
  });

  return {
    enabled,
    rate,
    pitch,
    volume,
    streaming,
    voices,
    supported,
    lastError,
    incrementalStreamingEnabled,
    refreshVoices,
    pushAssistantLiteral,
    pushAssistantSpecial,
    endAssistantStream,
    speak,
    stop,
  };
});
