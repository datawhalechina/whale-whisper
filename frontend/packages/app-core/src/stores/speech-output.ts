import { useLocalStorage } from "@vueuse/core";
import { defineStore, storeToRefs } from "pinia";
import { computed, onScopeDispose, ref, watch } from "vue";

import { requestTts, resolveAudioApiBaseUrl } from "../services/audio";
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
  const audioApiBaseUrl = computed(() => resolveAudioApiBaseUrl());
  const useBrowserTts = computed(
    () => speechProviderId.value === "browser-local-audio-speech"
  );
  const supported = computed(() => {
    if (typeof window === "undefined") return false;
    if (useBrowserTts.value) {
      return "speechSynthesis" in window;
    }
    return Boolean(audioApiBaseUrl.value);
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

  async function requestTtsSerial(params: Parameters<typeof requestTts>[0]) {
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
      return await requestTts(params);
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

  async function requestTtsWithRetry(params: Parameters<typeof requestTts>[0]) {
    const maxAttempts = 3;
    for (let attempt = 1; attempt <= maxAttempts; attempt++) {
      try {
        return await requestTtsSerial(params);
      } catch (error) {
        const shouldRetry = attempt < maxAttempts && isRetriableTtsError(error);
        if (!shouldRetry) {
          throw error;
        }
        await sleep(180 * attempt, params.signal);
      }
    }
    throw new Error("TTS request failed.");
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

  function stopRemotePlayback() {
    if (remoteController) {
      remoteController.abort();
      remoteController = null;
    }
    stopStreamingPlayback();
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

  function buildRemoteConfig() {
    const config: Record<string, unknown> = {
      ...(providerConfig.value?.extra ?? {}),
    };
    const isAlibaba = speechProviderId.value === "alibaba-cloud-model-studio-speech";
    if (providerConfig.value?.apiKey) {
      config.apiKey = providerConfig.value.apiKey;
    }
    if (providerConfig.value?.baseUrl) {
      config.baseUrl = providerConfig.value.baseUrl;
    }
    let model = providerConfig.value?.model;
    const voice = resolvedVoiceId.value;
    if (model) {
      if (isAlibaba && !model.includes("/")) {
        model = `alibaba/${model}`;
      }
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
    return config;
  }

  const keptPunctuations = new Set(["?", "？", "!", "！"]);
  const hardPunctuations = new Set([".", "。", "?", "？", "!", "！", "…", "⋯", "～", "~", "\n", "\t", "\r"]);
  const softPunctuations = new Set([",", "，", "、", "–", "—", ":", "：", ";", "；", "《", "》", "「", "」"]);

  type SegmentLike = { segment?: string; isWordLike?: boolean };
  type SegmenterLike = { segment: (input: string) => Iterable<SegmentLike> };

  function createSegmenter(granularity: "word" | "grapheme"): SegmenterLike | null {
    const SegmenterCtor = (Intl as any)?.Segmenter as
      | (new (locales?: string | string[], options?: { granularity: string }) => SegmenterLike)
      | undefined;
    if (!SegmenterCtor) return null;
    try {
      return new SegmenterCtor(undefined, { granularity });
    } catch {
      return null;
    }
  }

  function splitGraphemes(text: string, segmenter: SegmenterLike | null) {
    if (!text) return [];
    if (!segmenter) {
      return Array.from(text);
    }
    const units: string[] = [];
    for (const token of segmenter.segment(text)) {
      if (typeof token?.segment === "string" && token.segment.length > 0) {
        units.push(token.segment);
      }
    }
    return units.length > 0 ? units : Array.from(text);
  }

  function countWordLike(text: string, segmenter: SegmenterLike | null) {
    if (!text) return 0;
    if (!segmenter) {
      const matched = text.match(/[A-Za-z0-9\u4e00-\u9fff]+/g);
      return matched?.length ?? 0;
    }
    let count = 0;
    for (const token of segmenter.segment(text)) {
      if (token?.isWordLike) {
        count += 1;
      }
    }
    return count;
  }

  function splitTtsText(text: string) {
    const source = text.trim();
    if (!source) return [];
    const graphemeSegmenter = createSegmenter("grapheme");
    const wordSegmenter = createSegmenter("word");
    const input = splitGraphemes(source, graphemeSegmenter);
    const boost = 2;
    const minimumWords = 4;
    const maximumWords = 12;
    const chunks: string[] = [];
    const emit = (value: string) => {
      const normalized = value.trim();
      if (normalized) {
        chunks.push(normalized);
      }
    };

    let yieldCount = 0;
    let buffer = "";
    let chunk = "";
    let chunkWordsCount = 0;
    let previousValue: string | undefined;

    for (let i = 0; i < input.length; i++) {
      let value = input[i];
      if (value.length > 1) {
        previousValue = value;
        continue;
      }

      const hard = hardPunctuations.has(value);
      const soft = softPunctuations.has(value);
      const kept = keptPunctuations.has(value);

      if (hard || soft) {
        if ((value === "." || value === ",") && previousValue !== undefined && /\d/.test(previousValue)) {
          const next = input[i + 1];
          if (next && /\d/.test(next)) {
            buffer += value;
            previousValue = value;
            continue;
          }
        } else if (value === "." && input[i + 1] === "." && input[i + 2] === ".") {
          value = "…";
          i += 2;
        }

        if (buffer.length === 0) {
          previousValue = value;
          continue;
        }

        const words = countWordLike(buffer, wordSegmenter);
        if (chunkWordsCount > minimumWords && chunkWordsCount + words > maximumWords) {
          emit(kept ? `${chunk.trim()}${value}` : chunk);
          yieldCount += 1;
          chunk = "";
          chunkWordsCount = 0;
        }

        chunk += buffer + value;
        chunkWordsCount += words;
        buffer = "";

        if (hard || chunkWordsCount > maximumWords || yieldCount < boost) {
          emit(chunk);
          yieldCount += 1;
          chunk = "";
          chunkWordsCount = 0;
        }

        previousValue = value;
        continue;
      }

      buffer += value;
      previousValue = value;
    }

    if (chunk.length > 0 || buffer.length > 0) {
      emit(`${chunk}${buffer}`);
    }
    return chunks;
  }

  async function fetchTtsBuffer(text: string, controller: AbortController, ctx: AudioContext) {
    const blob = await requestTtsWithRetry({
      baseUrl: audioApiBaseUrl.value,
      engineId: providerMetadata.value?.engineId,
      text,
      config: buildRemoteConfig(),
      signal: controller.signal,
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
    const chunks = splitTtsText(text);
    if (chunks.length === 0) return;

    scheduledTime = ctx.currentTime;

    try {
      for (let index = 0; index < chunks.length; index++) {
        if (index > 0) {
          await sleep(120, controller.signal);
        }
        const chunk = chunks[index];
        const buffer = await fetchTtsBuffer(chunk, controller, ctx);
        if (!buffer || controller.signal.aborted) return;
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
      const blob = await requestTtsWithRetry({
        baseUrl: audioApiBaseUrl.value,
        engineId: providerMetadata.value?.engineId,
        text,
        config: buildRemoteConfig(),
        signal: controller.signal,
      });
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
    refreshVoices,
    speak,
    stop,
  };
});
