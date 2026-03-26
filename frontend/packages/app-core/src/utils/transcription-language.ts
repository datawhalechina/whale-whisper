const DEFAULT_TRANSCRIPTION_LANGUAGE = "en-US";

function normalizeLocaleToken(value: string) {
  return value.trim().replace("_", "-");
}

export function normalizeTranscriptionLanguage(language: unknown) {
  if (typeof language !== "string") {
    return DEFAULT_TRANSCRIPTION_LANGUAGE;
  }
  const normalized = normalizeLocaleToken(language);
  if (!normalized) {
    return DEFAULT_TRANSCRIPTION_LANGUAGE;
  }
  const lower = normalized.toLowerCase();
  if (lower === "zh") return "zh-CN";
  if (lower === "en") return "en-US";
  return normalized;
}

export function resolveInitialTranscriptionLanguage(
  navigatorLanguage?: string | null
) {
  return normalizeTranscriptionLanguage(navigatorLanguage);
}
