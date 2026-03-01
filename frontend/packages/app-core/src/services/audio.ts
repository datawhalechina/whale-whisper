import { appConfig } from "../config";
import {
  buildLegacyTtsHttpRequest,
  buildDirectTtsHttpRequest,
  supportsDirectTts,
} from "../utils/tts-direct-request";

type AudioRequestConfig = Record<string, unknown>;

export type TtsRequest = {
  text: string;
  engineId?: string;
  config?: AudioRequestConfig;
  signal?: AbortSignal;
  baseUrl?: string;
};

export type AsrRequest = {
  audioBase64: string;
  engineId?: string;
  config?: AudioRequestConfig;
  signal?: AbortSignal;
  baseUrl?: string;
};

export type AsrStreamRequest = {
  engineId?: string;
  config?: AudioRequestConfig;
  baseUrl?: string;
  sampleRate?: number;
  channels?: number;
};

export type AsrStreamConnection = {
  ready: Promise<void>;
  result: Promise<Record<string, any>>;
  sendAudio: (buffer: ArrayBuffer) => void;
  stop: () => void;
  close: () => void;
};

export { buildDirectTtsHttpRequest, supportsDirectTts };

function createTtsHttpError(status: number, detail: string) {
  const error = new Error(detail || `Direct TTS request failed: ${status}`) as Error & {
    status?: number;
    detail?: string;
  };
  error.status = status;
  error.detail = detail || undefined;
  return error;
}

function decodeBase64Audio(base64: string, mimeType: string) {
  const cleaned = base64.trim().replace(/^data:[^;]+;base64,/, "");
  const binary = atob(cleaned);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return new Blob([bytes], { type: mimeType || "audio/mpeg" });
}

async function resolveTtsBlob(response: Response) {
  const contentType = (response.headers.get("Content-Type") || "").toLowerCase();
  if (!contentType.includes("application/json")) {
    return await response.blob();
  }

  const payload = (await response.json().catch(() => null)) as
    | {
        audioBase64?: unknown;
        audio_base64?: unknown;
        audio?: unknown;
        mimeType?: unknown;
        mime_type?: unknown;
        format?: unknown;
      }
    | null;
  const audioBase64 =
    (typeof payload?.audioBase64 === "string" && payload.audioBase64) ||
    (typeof payload?.audio_base64 === "string" && payload.audio_base64) ||
    (typeof payload?.audio === "string" && payload.audio) ||
    "";
  if (audioBase64) {
    const mimeType =
      (typeof payload?.mimeType === "string" && payload.mimeType) ||
      (typeof payload?.mime_type === "string" && payload.mime_type) ||
      (typeof payload?.format === "string" && `audio/${payload.format}`) ||
      "audio/mpeg";
    return decodeBase64Audio(audioBase64, mimeType);
  }

  throw new Error("TTS response JSON does not contain audio payload.");
}

export function resolveAudioApiBaseUrl() {
  const proxyUrl = appConfig.providers.proxyUrl?.trim();
  const apiBaseUrl = appConfig.providers.apiBaseUrl?.trim();
  const base = proxyUrl || apiBaseUrl || "";
  return base ? base.replace(/\/$/, "") : "";
}

function resolveAudioWsBaseUrl(baseUrl?: string) {
  const base = baseUrl?.trim() || resolveAudioApiBaseUrl();
  if (!base) return "";
  if (base.startsWith("ws://") || base.startsWith("wss://")) return base;
  if (base.startsWith("https://")) return `wss://${base.slice(8)}`;
  if (base.startsWith("http://")) return `ws://${base.slice(7)}`;
  return `ws://${base}`;
}

export async function requestTts(request: TtsRequest): Promise<Blob> {
  return await requestTtsDirect(request);
}

export async function requestTtsDirect(request: TtsRequest): Promise<Blob> {
  const apiBaseUrl = request.baseUrl?.trim() || resolveAudioApiBaseUrl();
  if (!apiBaseUrl) {
    throw new Error("Audio API base URL is not configured.");
  }

  const directRequest = buildDirectTtsHttpRequest({
    text: request.text,
    engineId: request.engineId,
    apiBaseUrl,
    config: request.config,
  });
  if (!directRequest) {
    throw new Error("Backend relay TTS request is not available for current config.");
  }

  const response = await fetch(directRequest.url, {
    method: "POST",
    headers: directRequest.headers,
    body: JSON.stringify(directRequest.body),
    signal: request.signal,
  });

  if (response.ok) {
    return await resolveTtsBlob(response);
  }

  if (response.status === 405) {
    const legacyRequest = buildLegacyTtsHttpRequest(directRequest);
    const legacyResponse = await fetch(legacyRequest.url, {
      method: "POST",
      headers: legacyRequest.headers,
      body: JSON.stringify(legacyRequest.body),
      signal: request.signal,
    });

    if (legacyResponse.ok) {
      return await resolveTtsBlob(legacyResponse);
    }

    const detail = await legacyResponse.text();
    throw createTtsHttpError(legacyResponse.status, detail);
  }

  const detail = await response.text();
  throw createTtsHttpError(response.status, detail);
}

export async function requestAsr(request: AsrRequest): Promise<Record<string, any>> {
  const baseUrl = request.baseUrl?.trim() || resolveAudioApiBaseUrl();
  if (!baseUrl) {
    throw new Error("Audio API base URL is not configured.");
  }

  const response = await fetch(`${baseUrl}/api/asr/engines`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      engine: request.engineId || "default",
      data: { audio_base64: request.audioBase64 },
      config: request.config ?? {},
    }),
    signal: request.signal,
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `ASR request failed: ${response.status}`);
  }

  return (await response.json()) as Record<string, any>;
}

export function openAsrStream(request: AsrStreamRequest): AsrStreamConnection {
  const wsBase = resolveAudioWsBaseUrl(request.baseUrl);
  if (!wsBase) {
    throw new Error("Audio API base URL is not configured.");
  }

  const ws = new WebSocket(`${wsBase}/api/asr/engines/stream`);
  ws.binaryType = "arraybuffer";

  let readyResolve: () => void;
  let readyReject: (reason?: unknown) => void;
  const ready = new Promise<void>((resolve, reject) => {
    readyResolve = resolve;
    readyReject = reject;
  });

  let resultResolve: (payload: Record<string, any>) => void;
  let resultReject: (reason?: unknown) => void;
  const result = new Promise<Record<string, any>>((resolve, reject) => {
    resultResolve = resolve;
    resultReject = reject;
  });

  ws.onopen = () => {
    ws.send(
      JSON.stringify({
        type: "start",
        engine: request.engineId || "default",
        config: request.config ?? {},
        sample_rate: request.sampleRate ?? 16000,
        channels: request.channels ?? 1,
      })
    );
    readyResolve();
  };

  ws.onerror = () => {
    const error = new Error("ASR stream error.");
    readyReject(error);
    resultReject(error);
  };

  ws.onmessage = (event) => {
    if (typeof event.data !== "string") return;
    try {
      const payload = JSON.parse(event.data) as Record<string, any>;
      if (payload.type === "result") {
        resultResolve(payload.data ?? payload.payload ?? payload);
      } else if (payload.type === "error") {
        resultReject(new Error(payload.error || "ASR stream error."));
      }
    } catch (err) {
      resultReject(err);
    }
  };

  ws.onclose = () => {
    readyReject(new Error("ASR stream closed."));
  };

  return {
    ready,
    result,
    sendAudio: (buffer: ArrayBuffer) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(buffer);
      }
    },
    stop: () => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "stop" }));
      }
    },
    close: () => {
      if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
        ws.close();
      }
    },
  };
}
