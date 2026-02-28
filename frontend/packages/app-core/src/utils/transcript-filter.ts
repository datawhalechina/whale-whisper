const WINDOWS_ABSOLUTE_PATH_RE =
  /^[a-zA-Z]:\\(?:[^\\/:*?"<>|\r\n]+\\)*[^\\/:*?"<>|\r\n]+$/;

export function sanitizeTranscript(value: string) {
  const trimmed = value.trim();
  if (!trimmed) {
    return "";
  }

  const normalizedPathCandidate = trimmed.replace(/\//g, "\\");
  if (WINDOWS_ABSOLUTE_PATH_RE.test(normalizedPathCandidate)) {
    return "";
  }

  return trimmed;
}

