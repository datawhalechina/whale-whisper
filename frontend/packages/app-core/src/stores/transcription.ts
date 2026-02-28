import { useLocalStorage } from "@vueuse/core";
import { defineStore, storeToRefs } from "pinia";
import { computed, onScopeDispose, ref, watch } from "vue";

import { openAsrStream, requestAsr, resolveAudioApiBaseUrl } from "../services/audio";
import {
  concatInt16,
  createAudioCaptureSession,
  pcm16ToWavBlob,
} from "../utils/audio-stream";
import { shouldAutoRestartBrowserRecognition } from "../utils/browser-recognition-restart";
import { sanitizeTranscript } from "../utils/transcript-filter";
import { useChatStore } from "./chat";
import { useHearingStore } from "./hearing";
import { useProvidersStore } from "./providers";
import { useSettingsStore } from "./settings";

type SpeechRecognitionCtor = new () => any;

type RecordingResult = {
  blob: Blob;
  mimeType: string;
};

type CaptureMode = "worklet" | "media";
const BROWSER_RECOGNITION_RESTART_DELAY_MS = 250;

export const useTranscriptionStore = defineStore("transcription", () => {
  const chatStore = useChatStore();
  const hearingStore = useHearingStore();
  const providersStore = useProvidersStore();
  const settingsStore = useSettingsStore();
  const { transcriptionProviderId } = storeToRefs(settingsStore);

  const enabled = useLocalStorage("whalewhisper/audio/transcription/enabled", false);
  const autoSend = useLocalStorage("whalewhisper/audio/transcription/auto-send", true);
  const language = useLocalStorage("whalewhisper/audio/transcription/language", "en-US");
  const vadMinSpeechMs = useLocalStorage(
    "whalewhisper/audio/transcription/vad-min-ms",
    300
  );
  const vadSilenceMs = useLocalStorage(
    "whalewhisper/audio/transcription/vad-silence-ms",
    700
  );
  const streamingEnabled = useLocalStorage(
    "whalewhisper/audio/transcription/streaming",
    true
  );

  const listening = ref(false);
  const audioApiBaseUrl = computed(() => resolveAudioApiBaseUrl());
  const speechRecognitionAvailable = computed(() => {
    if (typeof window === "undefined") return false;
    return "SpeechRecognition" in window || "webkitSpeechRecognition" in window;
  });
  const micMonitorAvailable = computed(() => {
    if (typeof window === "undefined") return false;
    return Boolean(navigator.mediaDevices?.getUserMedia);
  });
  const workletAvailable = computed(() => {
    if (typeof window === "undefined") return false;
    return typeof AudioWorkletNode !== "undefined";
  });
  const recordingAvailable = computed(() => {
    if (typeof window === "undefined") return false;
    return Boolean(
      navigator.mediaDevices?.getUserMedia && typeof MediaRecorder !== "undefined"
    );
  });
  const useBrowserRecognition = computed(
    () => transcriptionProviderId.value === "browser-local-audio-transcription"
  );
  const canListen = computed(
    () => speechRecognitionAvailable.value || micMonitorAvailable.value
  );
  const supported = computed(() => {
    if (useBrowserRecognition.value) {
      return speechRecognitionAvailable.value;
    }
    return Boolean(audioApiBaseUrl.value && (workletAvailable.value || recordingAvailable.value));
  });
  const useStreamingTransport = computed(
    () =>
      streamingEnabled.value &&
      Boolean(audioApiBaseUrl.value) &&
      workletAvailable.value
  );
  const interimText = ref("");
  const lastTranscript = ref("");
  const error = ref<string | null>(null);
  const vadActive = ref(false);

  let recognition: any = null;
  let recorder: MediaRecorder | null = null;
  let recorderStream: MediaStream | null = null;
  let recorderChunks: BlobPart[] = [];
  let recorderMimeType = "";
  let recorderStartedAt = 0;
  let silenceTimer: number | null = null;
  let restoreHearingEnabled: boolean | null = null;
  let browserRecognitionSessionRequested = false;
  let manualBrowserRecognitionStop = false;
  let recognitionRestartTimer: number | null = null;
  let lastBrowserRecognitionErrorCode: string | null = null;

  let captureSession: Awaited<ReturnType<typeof createAudioCaptureSession>> | null = null;
  let captureActive = false;
  let captureMode: CaptureMode | null = null;
  let captureChunks: Int16Array[] = [];
  let captureSamples = 0;
  let captureStartedAt = 0;
  let streamPending: ArrayBuffer[] = [];
  let streamConnection: ReturnType<typeof openAsrStream> | null = null;
  let streamReady = false;

  const minSpeechMs = computed(() =>
    Math.max(100, Number(vadMinSpeechMs.value) || 300)
  );
  const silenceStopMs = computed(() =>
    Math.max(200, Number(vadSilenceMs.value) || 700)
  );

  function applyTranscript(raw: string) {
    const transcript = sanitizeTranscript(raw);
    if (!transcript) {
      return;
    }
    lastTranscript.value = transcript;
    interimText.value = "";
    if (autoSend.value) {
      chatStore.send(transcript);
    }
  }

  function shouldRestartBrowserRecognition() {
    return shouldAutoRestartBrowserRecognition({
      userRequested: browserRecognitionSessionRequested,
      manuallyStopped: manualBrowserRecognitionStop,
      enabled: enabled.value,
      supported: supported.value,
      useBrowserRecognition: useBrowserRecognition.value,
      lastErrorCode: lastBrowserRecognitionErrorCode,
    });
  }

  function clearRecognitionRestartTimer() {
    if (typeof window === "undefined") return;
    if (recognitionRestartTimer) {
      window.clearTimeout(recognitionRestartTimer);
      recognitionRestartTimer = null;
    }
  }

  function startBrowserRecognitionSession() {
    const recognizer = ensureRecognition();
    if (!recognizer) return;
    recognizer.lang = language.value;
    try {
      recognizer.start();
    } catch (err) {
      const name = err instanceof DOMException ? err.name : "";
      if (name === "InvalidStateError") {
        listening.value = true;
        return;
      }
      error.value = err instanceof Error ? err.message : "Speech recognition error.";
      listening.value = false;
    }
  }

  function scheduleBrowserRecognitionRestart() {
    if (typeof window === "undefined") return;
    clearRecognitionRestartTimer();
    recognitionRestartTimer = window.setTimeout(() => {
      recognitionRestartTimer = null;
      if (!shouldRestartBrowserRecognition()) {
        listening.value = false;
        return;
      }
      startBrowserRecognitionSession();
    }, BROWSER_RECOGNITION_RESTART_DELAY_MS);
  }

  function getRecognitionCtor(): SpeechRecognitionCtor | null {
    if (typeof window === "undefined") return null;
    return (window.SpeechRecognition || window.webkitSpeechRecognition) as SpeechRecognitionCtor;
  }

  function ensureRecognition() {
    if (!supported.value || !useBrowserRecognition.value) {
      return null;
    }

    if (recognition) {
      return recognition;
    }

    const Ctor = getRecognitionCtor();
    if (!Ctor) {
      return null;
    }

    recognition = new Ctor();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = language.value;

    recognition.onstart = () => {
      listening.value = true;
      error.value = null;
      lastBrowserRecognitionErrorCode = null;
    };

    recognition.onend = () => {
      if (shouldRestartBrowserRecognition()) {
        listening.value = true;
        scheduleBrowserRecognitionRestart();
        return;
      }
      listening.value = false;
    };

    recognition.onerror = (event) => {
      lastBrowserRecognitionErrorCode =
        typeof event.error === "string" ? event.error : null;
      error.value = event.error || "Speech recognition error.";
      listening.value = false;
    };

    recognition.onresult = (event) => {
      let finalText = "";
      let interim = "";

      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const result = event.results[i];
        const text = result[0]?.transcript ?? "";
        if (result.isFinal) {
          finalText += text;
        } else {
          interim += text;
        }
      }

      interimText.value = sanitizeTranscript(interim);
      if (finalText.trim()) {
        applyTranscript(finalText);
      }
    };

    return recognition;
  }

  async function ensureCaptureSession() {
    if (captureSession) {
      await captureSession.resume();
      return captureSession;
    }

    if (!hearingStore.getStream()) {
      await hearingStore.start();
    }

    const stream = hearingStore.getStream();
    if (!stream) {
      throw new Error("Failed to acquire microphone stream.");
    }

    captureSession = await createAudioCaptureSession(stream, {
      sampleRate: 16000,
      onChunk: handleCaptureChunk,
    });

    return captureSession;
  }

  function handleCaptureChunk(pcm16: Int16Array) {
    if (!captureActive) return;
    captureSamples += pcm16.length;
    captureChunks.push(pcm16);

    if (streamConnection) {
      const buffer = pcm16.buffer.slice(0);
      if (streamReady) {
        streamConnection.sendAudio(buffer);
      } else {
        streamPending.push(buffer);
      }
    }
  }

  async function startListening() {
    if (!canListen.value) {
      error.value = useBrowserRecognition.value
        ? "Speech recognition is not supported in this environment."
        : "Microphone is not supported in this environment.";
      return;
    }

    if (!enabled.value) {
      enabled.value = true;
    }
    if (!autoSend.value) {
      autoSend.value = true;
    }

    listening.value = true;

    if (!hearingStore.enabled) {
      restoreHearingEnabled = false;
      hearingStore.enabled = true;
    }
    await hearingStore.start();

    if (useBrowserRecognition.value && supported.value) {
      browserRecognitionSessionRequested = true;
      manualBrowserRecognitionStop = false;
      lastBrowserRecognitionErrorCode = null;
      clearRecognitionRestartTimer();
      startBrowserRecognitionSession();
      return;
    }

    await startVad();
  }

  async function stopListening() {
    listening.value = false;

    if (useBrowserRecognition.value) {
      browserRecognitionSessionRequested = false;
      manualBrowserRecognitionStop = true;
      clearRecognitionRestartTimer();
      recognition?.stop();
    } else {
      await stopVad();
    }

    if (restoreHearingEnabled === false) {
      hearingStore.enabled = false;
    }
    restoreHearingEnabled = null;
  }

  function resolveRecorderMimeType() {
    if (typeof MediaRecorder === "undefined") return "";
    const candidates = [
      "audio/webm;codecs=opus",
      "audio/webm",
      "audio/ogg;codecs=opus",
      "audio/ogg",
      "audio/wav",
    ];
    return candidates.find((type) => MediaRecorder.isTypeSupported(type)) || "";
  }

  async function startRecording() {
    error.value = null;
    if (!navigator.mediaDevices?.getUserMedia) {
      error.value = "Microphone is not supported in this environment.";
      return;
    }
    if (recorder) return;

    const constraints: MediaStreamConstraints = {
      audio: hearingStore.selectedDeviceId
        ? { deviceId: { exact: hearingStore.selectedDeviceId } }
        : true,
    };
    try {
      recorderStream = await navigator.mediaDevices.getUserMedia(constraints);
    } catch (err) {
      error.value = err instanceof Error ? err.message : "Failed to access microphone.";
      return;
    }

    const mimeType = resolveRecorderMimeType();
    recorderMimeType = mimeType;
    recorderChunks = [];
    try {
      recorder = mimeType
        ? new MediaRecorder(recorderStream, { mimeType })
        : new MediaRecorder(recorderStream);
    } catch (err) {
      error.value = err instanceof Error ? err.message : "Failed to start recorder.";
      cleanupRecorder();
      return;
    }

    recorder.ondataavailable = (event) => {
      if (event.data && event.data.size > 0) {
        recorderChunks.push(event.data);
      }
    };
    recorder.onstart = () => {
      recorderStartedAt = Date.now();
      interimText.value = "";
      lastTranscript.value = "";
    };
    recorder.onerror = (event) => {
      const detail = (event as unknown as { error?: Error }).error;
      error.value = detail?.message || "Recorder error.";
    };
    recorder.start();
  }

  async function stopRecording() {
    if (!recorder) return;
    const stopped = await waitForRecorderStop();
    cleanupRecorder();
    if (!stopped) return;
    await transcribeRecording(stopped);
  }

  function waitForRecorderStop(): Promise<RecordingResult | null> {
    return new Promise((resolve) => {
      const target = recorder;
      if (!target) {
        resolve(null);
        return;
      }

      target.onstop = () => {
        const mimeType = recorderMimeType || "audio/webm";
        const blob = new Blob(recorderChunks, { type: mimeType });
        resolve({ blob, mimeType });
      };

      target.stop();
    });
  }

  function cleanupRecorder() {
    recorderChunks = [];
    recorderMimeType = "";
    if (recorderStream) {
      recorderStream.getTracks().forEach((track) => track.stop());
    }
    recorderStream = null;
    recorder = null;
  }

  async function transcribeRecording(result: RecordingResult) {
    if (!enabled.value) {
      return;
    }
    if (Date.now() - recorderStartedAt < minSpeechMs.value) {
      return;
    }
    if (!audioApiBaseUrl.value) {
      error.value = "Audio API base URL is not configured.";
      return;
    }

    try {
      const base64 = await blobToBase64(result.blob);
      const payload = await requestAsr({
        baseUrl: audioApiBaseUrl.value,
        engineId: providersStore.getProviderMetadata(transcriptionProviderId.value)?.engineId,
        audioBase64: base64,
        config: buildAsrConfig(result.mimeType),
      });
      const transcript = extractTranscript(payload);
      if (transcript) {
        applyTranscript(transcript);
      }
    } catch (err) {
      error.value = err instanceof Error ? err.message : "Transcription failed.";
    }
  }

  function buildAsrConfig(mimeType: string) {
    const config: Record<string, unknown> = {
      ...(providersStore.getProviderConfig(transcriptionProviderId.value)?.extra ?? {}),
    };
    const model = providersStore.getProviderConfig(transcriptionProviderId.value)?.model;
    if (model) {
      config.model = model;
    }
    if (language.value) {
      config.language = language.value;
    }
    const extension = resolveExtension(mimeType);
    config.filename = extension ? `audio.${extension}` : "audio.wav";
    config.content_type = mimeType || "application/octet-stream";
    return config;
  }

  function resolveExtension(mimeType: string) {
    const value = mimeType.toLowerCase();
    if (value.includes("webm")) return "webm";
    if (value.includes("ogg")) return "ogg";
    if (value.includes("wav")) return "wav";
    if (value.includes("mpeg") || value.includes("mp3")) return "mp3";
    if (value.includes("mp4") || value.includes("m4a")) return "m4a";
    return "";
  }

  function extractTranscript(payload: Record<string, any>) {
    if (typeof payload.text === "string") return sanitizeTranscript(payload.text);
    const data = payload.data;
    if (data && typeof data.text === "string") return sanitizeTranscript(data.text);
    return "";
  }

  async function blobToBase64(blob: Blob) {
    const buffer = await blob.arrayBuffer();
    const bytes = new Uint8Array(buffer);
    let binary = "";
    const chunkSize = 0x8000;
    for (let i = 0; i < bytes.length; i += chunkSize) {
      const chunk = bytes.subarray(i, i + chunkSize);
      binary += String.fromCharCode(...chunk);
    }
    return btoa(binary);
  }

  async function startVad() {
    if (vadActive.value) return;
    vadActive.value = true;
    listening.value = true;
    error.value = null;

    try {
      // Always use local volume-threshold detection to avoid external VAD runtime/CDN dependency.
      hearingStore.stopSpeechDetection();
      await hearingStore.start();
      if (workletAvailable.value) {
        await ensureCaptureSession();
      }
    } catch (err) {
      hearingStore.stopSpeechDetection();
      error.value =
        err instanceof Error
          ? err.message
          : "Failed to start microphone listening.";
    }
  }

  async function stopVad() {
    if (!vadActive.value) return;
    vadActive.value = false;
    hearingStore.stopSpeechDetection();
    if (silenceTimer) {
      window.clearTimeout(silenceTimer);
      silenceTimer = null;
    }
    await stopCapture();
  }

  async function startCapture() {
    if (captureActive) return;
    captureStartedAt = Date.now();
    captureChunks = [];
    captureSamples = 0;
    streamPending = [];
    streamReady = false;
    captureActive = true;

    if (workletAvailable.value) {
      await ensureCaptureSession();
      captureMode = "worklet";
      if (useStreamingTransport.value) {
        try {
          streamConnection = openAsrStream({
            baseUrl: audioApiBaseUrl.value,
            engineId: providersStore.getProviderMetadata(transcriptionProviderId.value)?.engineId,
            config: buildAsrConfig("audio/wav"),
            sampleRate: captureSession?.sampleRate ?? 16000,
            channels: 1,
          });
          streamConnection.ready
            .then(() => {
              streamReady = true;
              streamPending.forEach((buffer) => streamConnection?.sendAudio(buffer));
              streamPending = [];
            })
            .catch((err) => {
              error.value = err instanceof Error ? err.message : "ASR stream failed.";
              streamConnection = null;
            });
        } catch (err) {
          error.value = err instanceof Error ? err.message : "ASR stream failed.";
          streamConnection = null;
        }
      }
      return;
    }

    if (!recordingAvailable.value) {
      error.value = "Recording is not supported in this environment.";
      captureActive = false;
      return;
    }

    captureMode = "media";
    await startRecording();
  }

  async function stopCapture() {
    if (!captureActive) return;
    captureActive = false;

    if (captureMode === "media") {
      await stopRecording();
      captureMode = null;
      return;
    }

    const durationMs = captureSession
      ? (captureSamples / captureSession.sampleRate) * 1000
      : Date.now() - captureStartedAt;

    let streamSucceeded = false;
    if (streamConnection) {
      try {
        streamConnection.stop();
        const payload = await streamConnection.result;
        const transcript = extractTranscript(payload);
        if (transcript) {
          applyTranscript(transcript);
        }
        streamSucceeded = true;
      } catch (err) {
        error.value = err instanceof Error ? err.message : "ASR stream failed.";
      } finally {
        streamConnection.close();
        streamConnection = null;
      }
    }

    if (!streamSucceeded && enabled.value && durationMs >= minSpeechMs.value) {
      try {
        const pcm16 = concatInt16(captureChunks);
        const wavBlob = pcm16ToWavBlob(pcm16, captureSession?.sampleRate ?? 16000);
        const base64 = await blobToBase64(wavBlob);
        const payload = await requestAsr({
          baseUrl: audioApiBaseUrl.value,
          engineId: providersStore.getProviderMetadata(transcriptionProviderId.value)?.engineId,
          audioBase64: base64,
          config: buildAsrConfig("audio/wav"),
        });
        const transcript = extractTranscript(payload);
        if (transcript) {
          applyTranscript(transcript);
        }
      } catch (err) {
        error.value = err instanceof Error ? err.message : "Transcription failed.";
      }
    }

    captureChunks = [];
    captureSamples = 0;
    captureMode = null;
  }

  function handleVadState(isSpeaking: boolean) {
    if (!vadActive.value) return;
    if (isSpeaking) {
      if (silenceTimer) {
        window.clearTimeout(silenceTimer);
        silenceTimer = null;
      }
      if (!captureActive && supported.value && enabled.value) {
        void startCapture();
      }
      return;
    }

    if (captureActive && !silenceTimer) {
      silenceTimer = window.setTimeout(() => {
        silenceTimer = null;
        if (!hearingStore.speechDetected) {
          void stopCapture();
        }
      }, silenceStopMs.value);
    }
  }

  watch(language, (next) => {
    if (recognition) {
      recognition.lang = next;
    }
  });

  watch(enabled, (next) => {
    if (!next) {
      if (listening.value) {
        void stopListening();
      }
    }
  });

  watch(
    () => transcriptionProviderId.value,
    () => {
      void stopListening();
    }
  );

  watch(
    () => hearingStore.speechDetected,
    (speaking) => {
      handleVadState(speaking);
    }
  );

  onScopeDispose(() => {
    clearRecognitionRestartTimer();
    void stopListening();
    recognition = null;
    cleanupRecorder();
    if (silenceTimer) {
      window.clearTimeout(silenceTimer);
      silenceTimer = null;
    }
    if (captureSession) {
      void captureSession.stop();
      captureSession = null;
    }
  });

  watch(
    () => hearingStore.streaming,
    (active) => {
      if (active) return;
      if (captureSession) {
        void captureSession.stop();
        captureSession = null;
      }
    }
  );

  watch(
    () => hearingStore.selectedDeviceId,
    () => {
      if (captureSession) {
        void captureSession.stop();
        captureSession = null;
      }
    }
  );

  return {
    enabled,
    autoSend,
    language,
    vadMinSpeechMs,
    vadSilenceMs,
    listening,
    supported,
    canListen,
    interimText,
    lastTranscript,
    error,
    startListening,
    stopListening,
  };
});
